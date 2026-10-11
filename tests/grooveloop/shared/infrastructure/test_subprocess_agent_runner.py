from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec, patch

import pytest

from grooveloop.shared.domain.agent_command import AgentCommand
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.infrastructure.claude_command import ClaudeCommand
from grooveloop.shared.infrastructure.claude_log_reader import ClaudeLogReader
from grooveloop.shared.infrastructure.git_command_error import GitCommandError
from grooveloop.shared.infrastructure.opencode_log_reader import OpencodeLogReader
from grooveloop.shared.infrastructure.subprocess_agent_runner import SubprocessAgentRunner
from tests.playground.shared.infrastructure.clock import clock_at

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_log_reader import AgentLogReader

_NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
_LOG_READERS: dict[str, AgentLogReader] = {"claude": ClaudeLogReader(), "opencode": OpencodeLogReader()}


def _stub_command() -> Any:
    command = create_autospec(AgentCommand, spec_set=True, instance=True)
    command.engine = "stub-engine"
    command.argv.side_effect = lambda model: ["stub-agent", "--model", model]
    command.resume_argv.return_value = None

    return command


def _launched(pid: int) -> Any:
    process = create_autospec(subprocess.Popen, instance=True)
    process.pid = pid

    return process


def _run_git(*args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
    )


def _make_base_repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    base = tmp_path / "base"
    _run_git("init", "--bare", "-b", "master", str(origin))
    _run_git("clone", str(origin), str(base))
    (base / "README.md").write_text("base\n")
    _run_git("-C", str(base), "add", ".")
    _run_git("-C", str(base), "commit", "-m", "init")
    _run_git("-C", str(base), "push", "origin", "master")

    return base


def _commit_of(repo: Path, revision: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", revision],
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


@pytest.mark.integration
class TestSubprocessAgentRunnerDispatch:
    def test_dispatch_should_launch_detached_and_return_the_pid(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(4242)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "implement the slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        assert run.pid == 4242
        _, kwargs = popen.call_args
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["close_fds"] is True

    def test_dispatch_should_hand_the_bash_timeouts_to_claude_when_the_loop_environment_lacks_them(
        self, tmp_path: Path
    ) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in ("BASH_DEFAULT_TIMEOUT_MS", "BASH_MAX_TIMEOUT_MS")
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen,
        ):
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            runner.dispatch(
                "implement the slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        args, kwargs = popen.call_args
        script = args[0][2]
        assert "BASH_DEFAULT_TIMEOUT_MS" not in kwargs["env"]
        assert '"BASH_DEFAULT_TIMEOUT_MS": "600000"' in script
        assert '"BASH_MAX_TIMEOUT_MS": "3600000"' in script

    def test_dispatch_should_run_the_agent_in_a_worktree_named_after_the_slice_and_the_run(
        self, tmp_path: Path
    ) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "implement the slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        worktree = runs_dir / run.run_id / f"s12-{run.run_id[:8]}"
        assert worktree.is_dir()
        assert (worktree / ".git").exists()
        _, kwargs = popen.call_args
        assert kwargs["cwd"] == str(worktree)

    def test_dispatch_should_base_the_worktree_on_the_latest_master(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        _run_git("-C", str(base), "checkout", "-b", "leftover-from-previous-dispatch")
        (base / "leftover.txt").write_text("stale\n")
        _run_git("-C", str(base), "add", ".")
        _run_git("-C", str(base), "commit", "-m", "leftover work")
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "implement the slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        worktree = runs_dir / run.run_id / f"s12-{run.run_id[:8]}"
        assert _commit_of(worktree, "HEAD") == _commit_of(base, "origin/master")
        assert not (worktree / "leftover.txt").exists()

    def test_dispatch_should_name_the_worktrees_of_two_runs_of_the_same_slice_differently(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            first = runner.dispatch(
                "first slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )
            second = runner.dispatch(
                "second slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        first_worktree = Path(json.loads((runs_dir / first.run_id / "run.json").read_text())["workdir"])
        second_worktree = Path(json.loads((runs_dir / second.run_id / "run.json").read_text())["workdir"])
        assert first_worktree.name != second_worktree.name
        assert first_worktree.is_dir()
        assert second_worktree.is_dir()

    def test_dispatch_should_write_log_files_under_the_run_dir(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "implement the slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        assert (runs_dir / run.run_id / "agent.log").exists()
        assert (runs_dir / run.run_id / "agent.err").exists()

    def test_dispatch_should_wrap_the_argv_of_the_given_command_with_an_exit_marker(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(7)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=_stub_command(), log_readers=_LOG_READERS
            )

            runner.dispatch(
                "implement the slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        argv = popen.call_args.args[0]
        assert argv[0:3] == ["/bin/sh", "-c", argv[2]]
        assert "stub-agent --model opus" in argv[2]
        assert "[AGENT_EXIT]" in argv[2]
        assert argv[-1] == "implement the slice"

    def test_dispatch_should_write_run_metadata_with_task_type_and_started_at(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.ADDRESS_REVIEW,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        metadata = json.loads((runs_dir / run.run_id / "run.json").read_text())
        assert metadata["task_type"] == "address_review"
        assert metadata["started_at"] == _NOW.isoformat()
        assert metadata["slice_id"] == "12"
        assert metadata["repo"] == "owner/repo"
        assert metadata["engine"] == "claude"

    def test_dispatch_should_write_run_metadata_with_the_absolute_path_of_the_worktree(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        metadata = json.loads((runs_dir / run.run_id / "run.json").read_text())
        assert metadata["workdir"] == str((runs_dir / run.run_id / f"s12-{run.run_id[:8]}").resolve())

    def test_dispatch_should_write_run_metadata_with_the_pid_of_the_launched_process(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(4242)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        metadata = json.loads((runs_dir / run.run_id / "run.json").read_text())
        assert metadata["pid"] == 4242
        assert metadata["task_type"] == "implement_slice"

    def test_dispatch_should_name_the_run_dir_in_the_command_line_of_the_launched_process(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=_stub_command(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "implement the slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        assert str(runs_dir / run.run_id) in popen.call_args.args[0]

    def test_dispatch_should_write_run_metadata_with_the_engine_of_the_given_command(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=_stub_command(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        metadata = json.loads((runs_dir / run.run_id / "run.json").read_text())
        assert metadata["engine"] == "stub-engine"

    def test_dispatch_should_write_run_metadata_with_the_launch_model(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        metadata = json.loads((runs_dir / run.run_id / "run.json").read_text())
        assert metadata["launch_model"] == "opus"

    def test_dispatch_should_pass_the_launch_model_to_the_agent_command(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        argv = popen.call_args.args[0]
        assert "--model opus" in argv[2]

    def test_dispatch_should_pass_the_given_model_to_the_command_and_metadata(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="sonnet",
            )

        argv = popen.call_args.args[0]
        assert "--model sonnet" in argv[2]
        metadata = json.loads((runs_dir / run.run_id / "run.json").read_text())
        assert metadata["launch_model"] == "sonnet"

    def test_dispatch_should_write_run_metadata_with_the_story_id(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
                story_id="10",
                profile="developer",
            )

        metadata = json.loads((runs_dir / run.run_id / "run.json").read_text())
        assert metadata["story_id"] == "10"
        assert metadata["profile"] == "developer"

    def test_dispatch_should_write_run_metadata_with_a_null_story_id_when_not_given(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        metadata = json.loads((runs_dir / run.run_id / "run.json").read_text())
        assert metadata["story_id"] is None
        assert metadata["profile"] is None

    def test_dispatch_should_export_the_run_id_to_the_subprocess_environment(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        _, kwargs = popen.call_args
        assert kwargs["env"]["GROOVELOOP_RUN_ID"] == run.run_id

    def test_dispatch_should_preserve_the_rest_of_the_parent_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOME_PARENT_VAR", "kept")
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        _, kwargs = popen.call_args
        assert kwargs["env"]["SOME_PARENT_VAR"] == "kept"


def _registered_worktrees(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )

    return [line.removeprefix("worktree ") for line in result.stdout.splitlines() if line.startswith("worktree ")]


def _break_post_checkout_hook(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "post-checkout"
    hook.write_text("#!/bin/sh\necho 'checkout hook exploded' >&2\nexit 1\n")
    hook.chmod(0o755)


@pytest.mark.integration
class TestSubprocessAgentRunnerFailedDispatch:
    def test_dispatch_should_leave_no_run_dir_when_the_fetch_fails(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        _run_git("-C", str(base), "remote", "set-url", "origin", str(tmp_path / "gone.git"))
        runs_dir = tmp_path / "runs"
        runner = SubprocessAgentRunner(
            runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        with pytest.raises(GitCommandError):
            runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        assert list(runs_dir.iterdir()) == []

    def test_dispatch_should_name_the_git_command_and_its_stderr_when_the_fetch_fails(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        _run_git("-C", str(base), "remote", "set-url", "origin", str(tmp_path / "gone.git"))
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path / "runs", clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        with pytest.raises(GitCommandError) as error:
            runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        message = str(error.value)
        assert f"git -C {base} fetch origin master" in message
        assert "exit 128" in message
        assert "gone.git" in message

    def test_dispatch_should_leave_no_run_dir_nor_registered_worktree_when_the_worktree_add_fails(
        self, tmp_path: Path
    ) -> None:
        base = _make_base_repo(tmp_path)
        _break_post_checkout_hook(base)
        runs_dir = tmp_path / "runs"
        runner = SubprocessAgentRunner(
            runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        with pytest.raises(GitCommandError) as error:
            runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        assert "worktree add" in str(error.value)
        assert "checkout hook exploded" in str(error.value)
        assert list(runs_dir.iterdir()) == []
        assert _registered_worktrees(base) == [str(base.resolve())]

    def test_dispatch_should_leave_no_run_dir_nor_registered_worktree_when_the_launch_fails(
        self, tmp_path: Path
    ) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        runner = SubprocessAgentRunner(
            runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.side_effect = OSError("no such shell")
            with pytest.raises(OSError, match="no such shell"):
                runner.dispatch(
                    "slice",
                    workdir=str(base),
                    task_type=AgentTaskType.IMPLEMENT_SLICE,
                    slice_id="12",
                    repo="owner/repo",
                    model="opus",
                )

        assert list(runs_dir.iterdir()) == []
        assert _registered_worktrees(base) == [str(base.resolve())]

    def test_dispatch_should_leave_the_same_files_as_before_when_it_succeeds(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(1)
            runner = SubprocessAgentRunner(
                runs_dir=runs_dir, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
            )

            run = runner.dispatch(
                "slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )

        assert sorted(p.name for p in (runs_dir / run.run_id).iterdir()) == [
            "agent.err",
            "agent.log",
            "run.json",
            f"s12-{run.run_id[:8]}",
        ]


@pytest.mark.integration
class TestSubprocessAgentRunnerOutcome:
    def test_outcome_of_is_running_when_there_is_no_exit_marker(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        (run_dir / "agent.log").write_text("working on it\n")

        assert runner.outcome_of("run-1") == AgentOutcome.RUNNING

    def test_outcome_of_is_running_when_the_run_dir_is_missing(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        assert runner.outcome_of("unknown-run") == AgentOutcome.RUNNING

    def test_outcome_of_is_succeeded_when_the_exit_marker_is_zero(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        (run_dir / "agent.log").write_text("done\n[AGENT_EXIT] 0\n")

        assert runner.outcome_of("run-1") == AgentOutcome.SUCCEEDED

    def test_outcome_of_is_failed_when_the_log_declares_an_unknown_cause(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        result = json.dumps({"type": "result", "is_error": True, "result": "boom"})
        (run_dir / "agent.log").write_text(f"{result}\n[AGENT_EXIT] 1\n")

        assert runner.outcome_of("run-1") == AgentOutcome.FAILED

    def test_outcome_of_is_interrupted_when_the_log_declares_a_recoverable_cause(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        result = json.dumps({"type": "result", "is_error": True, "api_error_status": 529, "result": "Overloaded"})
        (run_dir / "agent.log").write_text(f"{result}\n[AGENT_EXIT] 1\n")

        assert runner.outcome_of("run-1") == AgentOutcome.INTERRUPTED

    def test_outcome_of_reads_the_log_with_the_reader_of_the_engine_of_the_run(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(json.dumps({"engine": "opencode"}))
        (run_dir / "agent.log").write_text("working\n[AGENT_EXIT] 143\n")

        assert runner.outcome_of("run-1") == AgentOutcome.INTERRUPTED


@pytest.mark.integration
class TestSubprocessAgentRunnerVerdict:
    def test_verdict_of_declares_the_cause_and_the_end_instant_of_a_finished_run(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        result = json.dumps({"type": "result", "is_error": True, "api_error_status": 529, "result": "Overloaded"})
        log = run_dir / "agent.log"
        log.write_text(f"{result}\n[AGENT_EXIT] 1\n")
        os.utime(log, (_NOW.timestamp(), _NOW.timestamp()))

        assert runner.verdict_of("run-1") == AgentRunVerdict(
            AgentOutcome.INTERRUPTED, AgentRunCause.OVERLOADED, finished_at=_NOW
        )

    def test_verdict_of_has_no_end_instant_while_the_run_is_running(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        (run_dir / "agent.log").write_text("working on it\n")

        assert runner.verdict_of("run-1") == AgentRunVerdict(AgentOutcome.RUNNING)


def _exited_pid() -> int:
    process = subprocess.Popen(["true"])
    process.wait()

    return process.pid


def _run_dir_launched_by(tmp_path: Path, pid: int) -> Path:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(json.dumps({"engine": "claude", "pid": pid}))
    (run_dir / "agent.log").write_text("working on it\n")

    return run_dir


def _silence_log_for(run_dir: Path, silence: timedelta) -> None:
    last_write = (_NOW - silence).timestamp()
    os.utime(run_dir / "agent.log", (last_write, last_write))


def _launch_run_process(run_dir: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(["/bin/sh", "-c", "sleep 30; true", str(run_dir)], start_new_session=True)


@pytest.mark.integration
class TestSubprocessAgentRunnerUnfinishedRun:
    def test_verdict_of_leaves_running_and_untouched_a_run_whose_process_vanished(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = _run_dir_launched_by(tmp_path, _exited_pid())

        verdict = runner.verdict_of("run-1")

        assert verdict == AgentRunVerdict(AgentOutcome.RUNNING)
        assert (run_dir / "agent.log").read_text() == "working on it\n"

    def test_verdict_of_sends_no_signal_to_a_run_silent_for_thirty_minutes(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        process = _launch_run_process(tmp_path / "run-1")
        try:
            run_dir = _run_dir_launched_by(tmp_path, process.pid)
            _silence_log_for(run_dir, timedelta(minutes=30))

            verdict = runner.verdict_of("run-1")
            still_running = process.poll() is None
        finally:
            process.kill()
            process.wait()

        assert verdict == AgentRunVerdict(AgentOutcome.RUNNING)
        assert still_running
        assert "[AGENT_EXIT]" not in (run_dir / "agent.log").read_text()

    def test_verdict_of_is_interrupted_by_vanishing_when_the_log_was_closed_as_vanished(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = _run_dir_launched_by(tmp_path, _exited_pid())
        (run_dir / "agent.log").write_text("working on it\n\n[AGENT_VANISHED]\n[AGENT_EXIT] 143\n")

        verdict = runner.verdict_of("run-1")

        assert (verdict.outcome, verdict.cause) == (AgentOutcome.INTERRUPTED, AgentRunCause.VANISHED)
        assert verdict.finished_at is not None

    def test_verdict_of_is_interrupted_by_stalling_when_the_log_was_closed_as_stalled(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path, clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )
        run_dir = _run_dir_launched_by(tmp_path, _exited_pid())
        (run_dir / "agent.log").write_text("working on it\n\n[AGENT_STALLED]\n[AGENT_EXIT] 143\n")

        verdict = runner.verdict_of("run-1")

        assert (verdict.outcome, verdict.cause) == (AgentOutcome.INTERRUPTED, AgentRunCause.STALLED)


def _worktree_on_branch(tmp_path: Path, run_id: str, branch: str) -> Path:
    base = _make_base_repo(tmp_path)
    worktree = tmp_path / "runs" / run_id / "workdir"
    _run_git("-C", str(base), "worktree", "add", "-b", branch, str(worktree), "origin/master")

    return worktree


@pytest.mark.integration
class TestSubprocessAgentRunnerPushedBranch:
    def test_pushed_branch_of_is_the_branch_of_the_run_worktree_when_it_reached_origin(self, tmp_path: Path) -> None:
        worktree = _worktree_on_branch(tmp_path, "run-1", "feat/previous-attempt")
        _run_git("-C", str(worktree), "push", "origin", "feat/previous-attempt")
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path / "runs", clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        assert runner.pushed_branch_of("run-1") == "feat/previous-attempt"

    def test_pushed_branch_of_is_none_when_the_branch_never_reached_origin(self, tmp_path: Path) -> None:
        _worktree_on_branch(tmp_path, "run-1", "feat/previous-attempt")
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path / "runs", clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        assert runner.pushed_branch_of("run-1") is None

    def test_pushed_branch_of_is_none_when_the_worktree_is_detached(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        worktree = tmp_path / "runs" / "run-1" / "workdir"
        _run_git("-C", str(base), "worktree", "add", "--detach", str(worktree), "origin/master")
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path / "runs", clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        assert runner.pushed_branch_of("run-1") is None

    def test_pushed_branch_of_is_none_when_the_run_has_no_worktree(self, tmp_path: Path) -> None:
        runner = SubprocessAgentRunner(
            runs_dir=tmp_path / "runs", clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
        )

        assert runner.pushed_branch_of("run-1") is None


def _finished_run(tmp_path: Path, run_id: str, engine: str = "claude", session_line: str | None = None) -> Path:
    worktree = _worktree_on_branch(tmp_path, run_id, "feat/previous-attempt")
    run_dir = worktree.parent
    metadata = {
        "task_type": "implement_slice",
        "started_at": "2026-06-30T11:00:00+00:00",
        "slice_id": "12",
        "repo": "owner/repo",
        "launch_model": "opus",
        "engine": engine,
        "story_id": "10",
        "profile": "developer",
        "pid": 99,
    }
    (run_dir / "run.json").write_text(json.dumps(metadata))
    session = session_line if session_line is not None else '{"type":"system","session_id":"session-1"}'
    (run_dir / "agent.log").write_text(f"{session}\n[AGENT_EXIT] 0\n")

    return run_dir


def _resuming_runner(tmp_path: Path) -> SubprocessAgentRunner:
    return SubprocessAgentRunner(
        runs_dir=tmp_path / "runs", clock=clock_at(_NOW), command=ClaudeCommand(), log_readers=_LOG_READERS
    )


@pytest.mark.integration
class TestSubprocessAgentRunnerResume:
    def test_resume_should_relaunch_the_session_of_the_previous_run_in_its_worktree(self, tmp_path: Path) -> None:
        previous = _finished_run(tmp_path, "run-1")
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(4343)

            run = _resuming_runner(tmp_path).resume("run-1", "open the pull request")

        assert run is not None
        assert run.pid == 4343
        assert run.run_id != "run-1"
        args, kwargs = popen.call_args
        script = args[0][2]
        assert "--resume session-1" in script
        assert args[0][4] == "open the pull request"
        assert kwargs["cwd"] == str(previous / "workdir")
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] is subprocess.DEVNULL

    def test_resume_should_write_a_new_run_dir_resumed_from_the_previous_run(self, tmp_path: Path) -> None:
        previous = _finished_run(tmp_path, "run-1")
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(4343)

            run = _resuming_runner(tmp_path).resume("run-1", "open the pull request")

        assert run is not None
        run_dir = tmp_path / "runs" / run.run_id
        metadata = json.loads((run_dir / "run.json").read_text())
        assert metadata == {
            "task_type": "implement_slice",
            "started_at": _NOW.isoformat(),
            "slice_id": "12",
            "repo": "owner/repo",
            "launch_model": "opus",
            "engine": "claude",
            "story_id": "10",
            "profile": "developer",
            "resumed_from": "run-1",
            "workdir": str((previous / "workdir").resolve()),
            "pid": 4343,
        }
        assert (run_dir / "agent.log").is_file()
        assert not (run_dir / "workdir").exists()

    def test_resume_should_relaunch_a_resumed_run_in_the_worktree_it_declares(self, tmp_path: Path) -> None:
        previous = _finished_run(tmp_path, "run-1")
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(4343)
            runner = _resuming_runner(tmp_path)
            first = runner.resume("run-1", "open the pull request")
            assert first is not None
            (tmp_path / "runs" / first.run_id / "agent.log").write_text(
                '{"type":"system","session_id":"session-2"}\n[AGENT_EXIT] 0\n'
            )

            second = runner.resume(first.run_id, "open the pull request")

        assert second is not None
        args, kwargs = popen.call_args
        assert "--resume session-2" in args[0][2]
        assert kwargs["cwd"] == str((previous / "workdir").resolve())

    def test_resume_should_relaunch_a_dispatched_run_in_the_worktree_named_after_its_slice_and_run(
        self, tmp_path: Path
    ) -> None:
        base = _make_base_repo(tmp_path)
        runner = _resuming_runner(tmp_path)
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(4343)
            previous = runner.dispatch(
                "implement the slice",
                workdir=str(base),
                task_type=AgentTaskType.IMPLEMENT_SLICE,
                slice_id="12",
                repo="owner/repo",
                model="opus",
            )
            (tmp_path / "runs" / previous.run_id / "agent.log").write_text(
                '{"type":"system","session_id":"session-1"}\n[AGENT_EXIT] 0\n'
            )

            resumed = runner.resume(previous.run_id, "open the pull request")

        assert resumed is not None
        _, kwargs = popen.call_args
        assert kwargs["cwd"] == str((tmp_path / "runs" / previous.run_id / f"s12-{previous.run_id[:8]}").resolve())

    def test_resume_should_be_none_when_the_previous_run_has_no_worktree(self, tmp_path: Path) -> None:
        previous = _finished_run(tmp_path, "run-1")
        _run_git("-C", str(tmp_path / "base"), "worktree", "remove", "--force", str(previous / "workdir"))

        assert _resuming_runner(tmp_path).resume("run-1", "open the pull request") is None
        assert [run_dir.name for run_dir in (tmp_path / "runs").iterdir()] == ["run-1"]

    def test_resume_should_be_none_when_the_log_of_the_previous_run_declares_no_session(self, tmp_path: Path) -> None:
        _finished_run(tmp_path, "run-1", session_line='{"type":"system"}')

        assert _resuming_runner(tmp_path).resume("run-1", "open the pull request") is None

    def test_resume_should_be_none_when_the_previous_run_ran_on_another_engine(self, tmp_path: Path) -> None:
        _finished_run(tmp_path, "run-1", engine="opencode")

        assert _resuming_runner(tmp_path).resume("run-1", "open the pull request") is None

    def test_resume_should_be_none_when_the_previous_run_is_missing(self, tmp_path: Path) -> None:
        assert _resuming_runner(tmp_path).resume("run-1", "open the pull request") is None

    def test_resume_should_leave_no_run_dir_and_keep_the_previous_worktree_when_the_launch_fails(
        self, tmp_path: Path
    ) -> None:
        previous = _finished_run(tmp_path, "run-1")
        with (
            patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen", side_effect=OSError("no exec")),
            pytest.raises(OSError, match="no exec"),
        ):
            _resuming_runner(tmp_path).resume("run-1", "open the pull request")

        assert [run_dir.name for run_dir in (tmp_path / "runs").iterdir()] == ["run-1"]
        assert (previous / "workdir").is_dir()

    def test_pushed_branch_of_a_resumed_run_is_the_branch_of_the_worktree_it_declares(self, tmp_path: Path) -> None:
        previous = _finished_run(tmp_path, "run-1")
        _run_git("-C", str(previous / "workdir"), "push", "origin", "feat/previous-attempt")
        with patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen") as popen:
            popen.return_value = _launched(4343)
            runner = _resuming_runner(tmp_path)
            resumed = runner.resume("run-1", "open the pull request")

        assert resumed is not None
        assert runner.pushed_branch_of(resumed.run_id) == "feat/previous-attempt"

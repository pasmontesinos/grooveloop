from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from subprocess import Popen
from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run import AgentRun
from grooveloop.shared.domain.agent_runner import AgentRunner
from grooveloop.shared.infrastructure.agent_exit_marker import exit_marker_command
from grooveloop.shared.infrastructure.agent_run_verdict_reader import read_run_engine, read_run_verdict
from grooveloop.shared.infrastructure.git_command_error import GitCommandError

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_command import AgentCommand
    from grooveloop.shared.domain.agent_log_reader import AgentLogReader
    from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
    from grooveloop.shared.domain.agent_task_type import AgentTaskType
    from grooveloop.shared.domain.clock import Clock

_BASE_BRANCH = "master"
_BASE_REVISION = f"origin/{_BASE_BRANCH}"
_METADATA_FILE = "run.json"
_LOG_FILE = "agent.log"
_LEGACY_WORKTREE_DIR = "workdir"
_STDERR_TAIL_LINES = 5
_SESSION_HEAD_BYTES = 65_536


class SubprocessAgentRunner(AgentRunner):
    def __init__(
        self, runs_dir: Path, clock: Clock, command: AgentCommand, log_readers: dict[str, AgentLogReader]
    ) -> None:
        self._runs_dir = runs_dir
        self._clock = clock
        self._command = command
        self._log_readers = log_readers

    def dispatch(
        self,
        instruction: str,
        workdir: str,
        task_type: AgentTaskType,
        slice_id: str,
        repo: str,
        model: str,
        story_id: str | None = None,
        profile: str | None = None,
    ) -> AgentRun:
        run_id = str(uuid.uuid4())
        run_dir = self._runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        worktree = run_dir / f"s{slice_id}-{run_id[:8]}"

        try:
            self._write_metadata(run_dir, worktree, task_type, slice_id, repo, model, story_id, profile)
            process = self._launch(instruction, workdir, worktree, run_dir, run_id, model)
        except BaseException:
            self._discard_run(workdir, worktree, run_dir)
            raise

        self._record_pid(run_dir, process.pid)

        return AgentRun(run_id=run_id, pid=process.pid)

    def resume(self, previous_run_id: str, instruction: str) -> AgentRun | None:
        previous_dir = self._runs_dir / previous_run_id
        metadata_file = previous_dir / _METADATA_FILE
        if not metadata_file.is_file():
            return None

        metadata = json.loads(metadata_file.read_text())
        worktree = _worktree_of(previous_dir)
        if metadata.get("engine") != self._command.engine or not worktree.is_dir():
            return None

        argv = self._command.resume_argv(str(metadata.get("launch_model")), _log_head(previous_dir / _LOG_FILE))
        if argv is None:
            return None

        run_id = str(uuid.uuid4())
        run_dir = self._runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._write_resumed_metadata(run_dir, metadata, previous_run_id, worktree)
            process = self._spawn(argv, instruction, worktree, run_dir, run_id)
        except BaseException:
            shutil.rmtree(run_dir, ignore_errors=True)
            raise

        self._record_pid(run_dir, process.pid)

        return AgentRun(run_id=run_id, pid=process.pid)

    def _write_resumed_metadata(
        self, run_dir: Path, previous: dict[str, object], previous_run_id: str, worktree: Path
    ) -> None:
        metadata = {key: value for key, value in previous.items() if key not in ("pid", "resumed_from", "workdir")}
        metadata |= {
            "started_at": self._clock.now().isoformat(),
            "resumed_from": previous_run_id,
            "workdir": str(worktree.resolve()),
        }
        (run_dir / _METADATA_FILE).write_text(json.dumps(metadata))

    def _launch(
        self, instruction: str, workdir: str, worktree: Path, run_dir: Path, run_id: str, model: str
    ) -> Popen[bytes]:
        self._create_worktree(workdir, worktree)

        return self._spawn(self._command.argv(model), instruction, worktree, run_dir, run_id)

    def _spawn(self, argv: list[str], instruction: str, cwd: Path, run_dir: Path, run_id: str) -> Popen[bytes]:
        out_fd = os.open(str(run_dir / _LOG_FILE), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        err_fd = os.open(str(run_dir / "agent.err"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.fchmod(out_fd, 0o644)
        os.fchmod(err_fd, 0o644)

        script = f'{shlex.join(argv)} "$1"; {exit_marker_command()}'

        try:
            return Popen(
                ["/bin/sh", "-c", script, str(run_dir), instruction],
                cwd=str(cwd),
                env=os.environ | {"GROOVELOOP_RUN_ID": run_id},
                stdin=subprocess.DEVNULL,
                stdout=out_fd,
                stderr=err_fd,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            os.close(out_fd)
            os.close(err_fd)

    def _create_worktree(self, base_repo: str, worktree: Path) -> None:
        _git("-C", base_repo, "fetch", "origin", _BASE_BRANCH)
        _git("-C", base_repo, "worktree", "add", "--detach", str(worktree), _BASE_REVISION)

    def _discard_run(self, base_repo: str, worktree: Path, run_dir: Path) -> None:
        subprocess.run(
            ["git", "-C", base_repo, "worktree", "remove", "--force", str(worktree)],
            check=False,
            capture_output=True,
        )
        shutil.rmtree(run_dir, ignore_errors=True)

    def _write_metadata(
        self,
        run_dir: Path,
        worktree: Path,
        task_type: AgentTaskType,
        slice_id: str,
        repo: str,
        model: str,
        story_id: str | None,
        profile: str | None,
    ) -> None:
        metadata = {
            "task_type": task_type.value,
            "started_at": self._clock.now().isoformat(),
            "slice_id": slice_id,
            "repo": repo,
            "launch_model": model,
            "engine": self._command.engine,
            "story_id": story_id,
            "profile": profile,
            "workdir": str(worktree.resolve()),
        }
        (run_dir / _METADATA_FILE).write_text(json.dumps(metadata))

    def _record_pid(self, run_dir: Path, pid: int) -> None:
        metadata_file = run_dir / _METADATA_FILE
        metadata = json.loads(metadata_file.read_text())

        metadata_file.write_text(json.dumps(metadata | {"pid": pid}))

    def outcome_of(self, run_id: str) -> AgentOutcome:
        run_dir = self._runs_dir / run_id

        return read_run_verdict(run_dir, read_run_engine(run_dir), self._log_readers).outcome

    def verdict_of(self, run_id: str) -> AgentRunVerdict:
        run_dir = self._runs_dir / run_id
        verdict = read_run_verdict(run_dir, read_run_engine(run_dir), self._log_readers)
        if verdict.outcome is AgentOutcome.RUNNING:
            return verdict

        finished_at = datetime.fromtimestamp((run_dir / _LOG_FILE).stat().st_mtime, UTC)

        return replace(verdict, finished_at=finished_at)

    def pushed_branch_of(self, run_id: str) -> str | None:
        worktree = _worktree_of(self._runs_dir / run_id)
        if not worktree.is_dir():
            return None

        branch = subprocess.run(
            ["git", "-C", str(worktree), "symbolic-ref", "--quiet", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if branch.returncode != 0:
            return None

        name = branch.stdout.strip()
        remote = subprocess.run(
            ["git", "-C", str(worktree), "ls-remote", "--exit-code", "--heads", "origin", name],
            check=False,
            capture_output=True,
        )

        return name if remote.returncode == 0 else None


def _worktree_of(run_dir: Path) -> Path:
    metadata_file = run_dir / _METADATA_FILE
    workdir = json.loads(metadata_file.read_text()).get("workdir") if metadata_file.is_file() else None

    return Path(workdir) if isinstance(workdir, str) else run_dir / _LEGACY_WORKTREE_DIR


def _log_head(log: Path) -> str:
    if not log.is_file():
        return ""

    with log.open("rb") as log_file:
        return log_file.read(_SESSION_HEAD_BYTES).decode(errors="replace")


def _git(*args: str) -> None:
    command = ["git", *args]
    result = subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.strip().splitlines()[-_STDERR_TAIL_LINES:])
        raise GitCommandError(f"`{shlex.join(command)}` failed with exit {result.returncode}:\n{stderr_tail}")

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.local_agent_workspaces import LocalAgentWorkspaces

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


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


def _make_run(
    runs_dir: Path,
    run_id: str,
    log: str | None = None,
    metadata: str = "{}",
    minutes_since_last_log_write: int = 31,
) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(metadata)
    (run_dir / "usage.json").write_text("{}")
    if log is not None:
        (run_dir / "agent.log").write_text(log)
        last_write = (_NOW - timedelta(minutes=minutes_since_last_log_write)).timestamp()
        os.utime(run_dir / "agent.log", (last_write, last_write))

    return run_dir


def _workspaces(runs_dir: Path) -> LocalAgentWorkspaces:
    clock: Any = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = _NOW

    return LocalAgentWorkspaces(runs_dir=runs_dir, clock=clock)


def _make_worktree(base: Path, run_dir: Path) -> Path:
    worktree = run_dir / "workdir"
    _run_git("-C", str(base), "worktree", "add", "--detach", str(worktree), "origin/master")

    return worktree


@pytest.mark.integration
class TestLocalAgentWorkspaces:
    def test_lists_the_run_of_a_finished_agent_that_keeps_its_workspace(self, tmp_path: Path) -> None:
        (_make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n") / "workdir").mkdir()

        assert _workspaces(tmp_path).finished_run_ids() == ["run-1"]

    def test_lists_the_run_of_a_scribe_that_belongs_to_no_slice(self, tmp_path: Path) -> None:
        run_dir = _make_run(
            tmp_path,
            "run-1",
            log="done\n[AGENT_EXIT] 0\n",
            metadata='{"task_type": "refine_conventions", "slice_id": ""}',
        )
        (run_dir / "workdir").mkdir()

        assert _workspaces(tmp_path).finished_run_ids() == ["run-1"]

    def test_does_not_list_a_run_that_finished_ten_minutes_ago(self, tmp_path: Path) -> None:
        run_dir = _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", minutes_since_last_log_write=10)
        (run_dir / "workdir").mkdir()

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_does_not_list_a_finished_run_whose_workspace_a_live_run_declares(self, tmp_path: Path) -> None:
        workspace = _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n") / "workdir"
        workspace.mkdir()
        _make_run(tmp_path, "run-2", log="working\n", metadata=json.dumps({"workdir": str(workspace)}))

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_lists_a_finished_run_whose_workspace_only_a_finished_run_declares(self, tmp_path: Path) -> None:
        workspace = _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n") / "workdir"
        workspace.mkdir()
        _make_run(tmp_path, "run-2", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(workspace)}))

        assert _workspaces(tmp_path).finished_run_ids() == ["run-1"]

    def test_does_not_list_a_finished_run_whose_workspace_a_run_finished_ten_minutes_ago_declares(
        self, tmp_path: Path
    ) -> None:
        workspace = (
            _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", minutes_since_last_log_write=40) / "workdir"
        )
        workspace.mkdir()
        _make_run(
            tmp_path,
            "run-2",
            log="done\n[AGENT_EXIT] 143\n",
            metadata=json.dumps({"workdir": str(workspace)}),
            minutes_since_last_log_write=10,
        )

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_lists_a_finished_run_whose_declared_workspace_has_another_name(self, tmp_path: Path) -> None:
        workspace = tmp_path / "run-1" / "s12-abcdefgh"
        _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(workspace)}))
        workspace.mkdir()

        assert _workspaces(tmp_path).finished_run_ids() == ["run-1"]

    def test_does_not_list_a_finished_run_whose_declared_workspace_a_live_run_declares(self, tmp_path: Path) -> None:
        workspace = tmp_path / "run-1" / "s12-abcdefgh"
        _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(workspace)}))
        workspace.mkdir()
        _make_run(tmp_path, "run-2", log="working\n", metadata=json.dumps({"workdir": str(workspace)}))

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_does_not_list_a_finished_run_whose_declared_workspace_is_outside_the_runs_dir(
        self, tmp_path: Path
    ) -> None:
        runs_dir = tmp_path / "runs"
        workspace = tmp_path / "elsewhere"
        workspace.mkdir()
        _make_run(runs_dir, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(workspace)}))

        assert _workspaces(runs_dir).finished_run_ids() == []

    def test_does_not_list_a_finished_run_whose_declared_workspace_is_the_runs_dir(self, tmp_path: Path) -> None:
        _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(tmp_path)}))

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_does_not_list_a_finished_run_whose_declared_workspace_is_a_run_dir(self, tmp_path: Path) -> None:
        other_run_dir = _make_run(tmp_path, "run-2", log="done\n[AGENT_EXIT] 0\n")
        _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(other_run_dir)}))

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_does_not_list_a_run_without_the_exit_marker(self, tmp_path: Path) -> None:
        (_make_run(tmp_path, "run-1", log="working\n") / "workdir").mkdir()

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_does_not_list_a_run_without_log(self, tmp_path: Path) -> None:
        (_make_run(tmp_path, "run-1") / "workdir").mkdir()

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_does_not_list_a_finished_run_without_workspace(self, tmp_path: Path) -> None:
        _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n")

        assert _workspaces(tmp_path).finished_run_ids() == []

    def test_lists_nothing_when_the_runs_dir_is_missing(self, tmp_path: Path) -> None:
        assert _workspaces(tmp_path / "missing").finished_run_ids() == []

    def test_remove_deletes_the_worktree_and_keeps_the_instrumentation(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        run_dir = _make_run(runs_dir, "run-1", log="done\n[AGENT_EXIT] 0\n")
        worktree = _make_worktree(base, run_dir)

        _workspaces(runs_dir).remove("run-1")

        assert not worktree.exists()
        listed = subprocess.run(
            ["git", "-C", str(base), "worktree", "list"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert str(worktree) not in listed
        assert (run_dir / "run.json").is_file()
        assert (run_dir / "agent.log").is_file()
        assert (run_dir / "usage.json").is_file()

    def test_remove_deletes_the_declared_worktree(self, tmp_path: Path) -> None:
        base = _make_base_repo(tmp_path)
        runs_dir = tmp_path / "runs"
        worktree = runs_dir / "run-1" / "s12-abcdefgh"
        _make_run(runs_dir, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(worktree)}))
        _run_git("-C", str(base), "worktree", "add", "--detach", str(worktree), "origin/master")

        _workspaces(runs_dir).remove("run-1")

        assert not worktree.exists()
        assert (runs_dir / "run-1" / "run.json").is_file()

    def test_remove_keeps_the_runs_dir_when_a_run_declares_it(self, tmp_path: Path) -> None:
        run_dir = _make_run(
            tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(tmp_path)})
        )

        _workspaces(tmp_path).remove("run-1")

        assert (run_dir / "run.json").is_file()
        assert (run_dir / "agent.log").is_file()

    def test_remove_is_idempotent_when_the_workspace_is_missing(self, tmp_path: Path) -> None:
        _workspaces(tmp_path).remove("unknown-run")

    def test_remove_deletes_a_workspace_that_is_no_longer_a_worktree(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        run_dir = _make_run(runs_dir, "run-1", log="done\n[AGENT_EXIT] 0\n")
        (run_dir / "workdir" / "src").mkdir(parents=True)

        _workspaces(runs_dir).remove("run-1")

        assert not (run_dir / "workdir").exists()
        assert (run_dir / "run.json").is_file()
        assert (run_dir / "agent.log").is_file()
        assert (run_dir / "usage.json").is_file()

    def test_remove_deletes_a_workspace_whose_git_link_is_broken(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        run_dir = _make_run(runs_dir, "run-1", log="done\n[AGENT_EXIT] 0\n")
        workspace = run_dir / "workdir"
        workspace.mkdir()
        (workspace / ".git").write_text(f"gitdir: {tmp_path / 'gone'}/.git/worktrees/workdir\n")

        _workspaces(runs_dir).remove("run-1")

        assert not workspace.exists()
        assert (run_dir / "run.json").is_file()

    def test_workspace_of_returns_the_declared_workspace(self, tmp_path: Path) -> None:
        workspace = tmp_path / "run-1" / "s12-abcdefgh"
        _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(workspace)}))
        workspace.mkdir()

        assert _workspaces(tmp_path).workspace_of("run-1") == str(workspace.resolve())

    def test_workspace_of_returns_the_workdir_of_a_run_without_the_declaration(self, tmp_path: Path) -> None:
        run_dir = _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n")
        (run_dir / "workdir").mkdir()

        assert _workspaces(tmp_path).workspace_of("run-1") == str((run_dir / "workdir").resolve())

    def test_workspace_of_returns_nothing_when_the_declared_workspace_is_outside_a_run_dir(
        self, tmp_path: Path
    ) -> None:
        _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n", metadata=json.dumps({"workdir": str(tmp_path)}))

        assert _workspaces(tmp_path).workspace_of("run-1") is None

    def test_workspace_of_returns_nothing_when_the_workspace_is_missing(self, tmp_path: Path) -> None:
        _make_run(tmp_path, "run-1", log="done\n[AGENT_EXIT] 0\n")

        assert _workspaces(tmp_path).workspace_of("run-1") is None

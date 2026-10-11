from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from grooveloop.shared.infrastructure.local_abandoned_agent_runs import LocalAbandonedAgentRuns
from tests.playground.shared.infrastructure.clock import clock_at

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
_REPO = "acme/sample"


def _exited_pid() -> int:
    process = subprocess.Popen(["true"])
    process.wait()

    return process.pid


def _run_dir_launched_by(tmp_path: Path, pid: int | None, run_id: str = "run-1", repo: str = _REPO) -> Path:
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    metadata: dict[str, object] = {"engine": "claude", "repo": repo}
    if pid is not None:
        metadata["pid"] = pid
    (run_dir / "run.json").write_text(json.dumps(metadata))
    (run_dir / "agent.log").write_text("working on it\n")

    return run_dir


def _silence_log_for(run_dir: Path, silence: timedelta) -> None:
    last_write = (_NOW - silence).timestamp()
    os.utime(run_dir / "agent.log", (last_write, last_write))


def _launch_run_process(run_dir: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(["/bin/sh", "-c", "sleep 30; true", str(run_dir)], start_new_session=True)


def _abandoned_runs(tmp_path: Path) -> LocalAbandonedAgentRuns:
    return LocalAbandonedAgentRuns(runs_dir=tmp_path, clock=clock_at(_NOW))


@pytest.mark.integration
class TestLocalAbandonedAgentRunsListing:
    def test_lists_the_run_of_the_repo_whose_process_vanished(self, tmp_path: Path) -> None:
        _run_dir_launched_by(tmp_path, _exited_pid())

        assert _abandoned_runs(tmp_path).abandoned_run_ids(_REPO) == ["run-1"]

    def test_lists_the_run_whose_pid_belongs_to_another_process(self, tmp_path: Path) -> None:
        _run_dir_launched_by(tmp_path, os.getpid())

        assert _abandoned_runs(tmp_path).abandoned_run_ids(_REPO) == ["run-1"]

    def test_lists_the_live_run_silent_for_thirty_minutes_without_signalling_it(self, tmp_path: Path) -> None:
        process = _launch_run_process(tmp_path / "run-1")
        try:
            run_dir = _run_dir_launched_by(tmp_path, process.pid)
            _silence_log_for(run_dir, timedelta(minutes=30))

            run_ids = _abandoned_runs(tmp_path).abandoned_run_ids(_REPO)
            still_running = process.poll() is None
        finally:
            process.kill()
            process.wait()

        assert run_ids == ["run-1"]
        assert still_running

    def test_skips_the_live_run_silent_for_twenty_nine_minutes(self, tmp_path: Path) -> None:
        process = _launch_run_process(tmp_path / "run-1")
        try:
            run_dir = _run_dir_launched_by(tmp_path, process.pid)
            _silence_log_for(run_dir, timedelta(minutes=29))

            run_ids = _abandoned_runs(tmp_path).abandoned_run_ids(_REPO)
        finally:
            process.kill()
            process.wait()

        assert run_ids == []

    def test_skips_the_run_that_wrote_its_exit_marker(self, tmp_path: Path) -> None:
        run_dir = _run_dir_launched_by(tmp_path, _exited_pid())
        (run_dir / "agent.log").write_text("done\n[AGENT_EXIT] 0\n")

        assert _abandoned_runs(tmp_path).abandoned_run_ids(_REPO) == []

    def test_skips_the_run_without_pid(self, tmp_path: Path) -> None:
        _run_dir_launched_by(tmp_path, None)

        assert _abandoned_runs(tmp_path).abandoned_run_ids(_REPO) == []

    def test_skips_the_run_of_another_repo(self, tmp_path: Path) -> None:
        _run_dir_launched_by(tmp_path, _exited_pid(), repo="acme/other")

        assert _abandoned_runs(tmp_path).abandoned_run_ids(_REPO) == []

    def test_skips_the_run_with_unreadable_metadata(self, tmp_path: Path) -> None:
        run_dir = _run_dir_launched_by(tmp_path, _exited_pid())
        (run_dir / "run.json").write_text("{not json")

        assert _abandoned_runs(tmp_path).abandoned_run_ids(_REPO) == []

    def test_lists_the_abandoned_runs_in_alphabetical_order(self, tmp_path: Path) -> None:
        _run_dir_launched_by(tmp_path, _exited_pid(), run_id="run-b")
        _run_dir_launched_by(tmp_path, _exited_pid(), run_id="run-a")

        assert _abandoned_runs(tmp_path).abandoned_run_ids(_REPO) == ["run-a", "run-b"]

    def test_lists_nothing_when_the_runs_directory_is_missing(self, tmp_path: Path) -> None:
        assert _abandoned_runs(tmp_path / "missing").abandoned_run_ids(_REPO) == []


@pytest.mark.integration
class TestLocalAbandonedAgentRunsClosing:
    def test_closes_the_log_of_a_vanished_run_with_the_vanished_and_exit_markers(self, tmp_path: Path) -> None:
        run_dir = _run_dir_launched_by(tmp_path, _exited_pid())

        _abandoned_runs(tmp_path).close("run-1")

        assert (run_dir / "agent.log").read_text().splitlines()[-2:] == ["[AGENT_VANISHED]", "[AGENT_EXIT] 143"]

    def test_closes_as_vanished_without_signalling_a_pid_whose_command_line_lacks_the_run_dir(
        self, tmp_path: Path
    ) -> None:
        process = _launch_run_process(tmp_path / "another-run")
        try:
            run_dir = _run_dir_launched_by(tmp_path, process.pid)
            _silence_log_for(run_dir, timedelta(hours=2))

            _abandoned_runs(tmp_path).close("run-1")
            still_running = process.poll() is None
        finally:
            process.kill()
            process.wait()

        assert (run_dir / "agent.log").read_text().splitlines()[-2:] == ["[AGENT_VANISHED]", "[AGENT_EXIT] 143"]
        assert still_running

    def test_terminates_and_closes_a_run_silent_for_thirty_minutes(self, tmp_path: Path) -> None:
        received = tmp_path / "received-signal"
        script = f"trap 'echo TERM > {received}; exit 143' TERM; echo ready; sleep 30; true"
        with subprocess.Popen(
            ["/bin/sh", "-c", script, str(tmp_path / "run-1")], stdout=subprocess.PIPE, start_new_session=True
        ) as process:
            try:
                assert process.stdout is not None
                process.stdout.readline()
                run_dir = _run_dir_launched_by(tmp_path, process.pid)
                _silence_log_for(run_dir, timedelta(minutes=30))

                _abandoned_runs(tmp_path).close("run-1")
            finally:
                process.kill()

        assert received.read_text() == "TERM\n"
        assert (run_dir / "agent.log").read_text().splitlines()[-2:] == ["[AGENT_STALLED]", "[AGENT_EXIT] 143"]

    def test_leaves_untouched_a_live_run_silent_for_twenty_nine_minutes(self, tmp_path: Path) -> None:
        process = _launch_run_process(tmp_path / "run-1")
        try:
            run_dir = _run_dir_launched_by(tmp_path, process.pid)
            _silence_log_for(run_dir, timedelta(minutes=29))

            _abandoned_runs(tmp_path).close("run-1")
            still_running = process.poll() is None
        finally:
            process.kill()
            process.wait()

        assert still_running
        assert (run_dir / "agent.log").read_text() == "working on it\n"

    def test_keeps_the_exit_marker_the_process_wrote_while_it_was_being_checked(self, tmp_path: Path) -> None:
        run_dir = _run_dir_launched_by(tmp_path, _exited_pid())

        def exit_while_checked(pid: int, checked_run_dir: Path) -> bool:
            with (checked_run_dir / "agent.log").open("a") as log:
                log.write("[AGENT_EXIT] 0\n")

            return False

        with patch(
            "grooveloop.shared.infrastructure.local_abandoned_agent_runs.is_run_process_alive",
            side_effect=exit_while_checked,
        ):
            _abandoned_runs(tmp_path).close("run-1")

        assert (run_dir / "agent.log").read_text() == "working on it\n[AGENT_EXIT] 0\n"

    def test_leaves_untouched_a_run_without_pid(self, tmp_path: Path) -> None:
        run_dir = _run_dir_launched_by(tmp_path, None)

        _abandoned_runs(tmp_path).close("run-1")

        assert (run_dir / "agent.log").read_text() == "working on it\n"

    def test_leaves_untouched_a_run_already_closed(self, tmp_path: Path) -> None:
        run_dir = _run_dir_launched_by(tmp_path, _exited_pid())
        (run_dir / "agent.log").write_text("done\n[AGENT_EXIT] 0\n")

        _abandoned_runs(tmp_path).close("run-1")

        assert (run_dir / "agent.log").read_text() == "done\n[AGENT_EXIT] 0\n"

    def test_does_nothing_for_a_missing_run(self, tmp_path: Path) -> None:
        _abandoned_runs(tmp_path).close("unknown-run")

        assert list(tmp_path.iterdir()) == []

from __future__ import annotations

import signal
import subprocess
from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.infrastructure.signal_workspace_processes import SignalWorkspaceProcesses

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def spawned() -> Iterator[list[subprocess.Popen[bytes]]]:
    processes: list[subprocess.Popen[bytes]] = []

    yield processes

    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait()


def _spawn(processes: list[subprocess.Popen[bytes]], cwd: Path, *argv: str) -> subprocess.Popen[bytes]:
    cwd.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(list(argv), cwd=cwd)
    processes.append(process)

    return process


@pytest.mark.integration
class TestSignalWorkspaceProcesses:
    def test_terminates_the_processes_whose_working_directory_is_within_the_workspace(
        self, tmp_path: Path, spawned: list[subprocess.Popen[bytes]]
    ) -> None:
        workspace = tmp_path / "s7-abcdef12"
        at_root = _spawn(spawned, workspace, "sleep", "3600")
        nested = _spawn(spawned, workspace / "web", "sleep", "3600")

        SignalWorkspaceProcesses(grace_seconds=5).terminate(str(workspace))

        assert at_root.wait(timeout=5) == -signal.SIGTERM
        assert nested.wait(timeout=5) == -signal.SIGTERM

    def test_leaves_alive_the_processes_whose_working_directory_is_outside_the_workspace(
        self, tmp_path: Path, spawned: list[subprocess.Popen[bytes]]
    ) -> None:
        workspace = tmp_path / "s7-abcdef12"
        workspace.mkdir()
        outside = _spawn(spawned, tmp_path / "s7-abcdef12-other", "sleep", "3600")

        SignalWorkspaceProcesses(grace_seconds=5).terminate(str(workspace))

        assert outside.poll() is None

    def test_kills_the_processes_that_survive_the_grace_period(
        self, tmp_path: Path, spawned: list[subprocess.Popen[bytes]]
    ) -> None:
        workspace = tmp_path / "s7-abcdef12"
        stubborn = _spawn(spawned, workspace, "sh", "-c", 'trap "" TERM; exec sleep 3600')

        SignalWorkspaceProcesses(grace_seconds=0.5).terminate(str(workspace))

        assert stubborn.wait(timeout=5) == -signal.SIGKILL

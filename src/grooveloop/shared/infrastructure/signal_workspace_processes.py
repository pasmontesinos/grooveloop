from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from grooveloop.shared.domain.workspace_processes import WorkspaceProcesses

_PROC_DIR = Path("/proc")
_LIST_TIMEOUT_SECONDS = 30
_POLL_SECONDS = 0.1
_DEFAULT_GRACE_SECONDS = 5.0


class SignalWorkspaceProcesses(WorkspaceProcesses):
    def __init__(self, grace_seconds: float = _DEFAULT_GRACE_SECONDS) -> None:
        self._grace_seconds = grace_seconds

    def terminate(self, workspace: str) -> None:
        root = Path(workspace).resolve()
        pids = self._pids_within(root)
        if not pids:
            return

        _signal(pids, signal.SIGTERM)

        deadline = time.monotonic() + self._grace_seconds
        while pids and time.monotonic() < deadline:
            time.sleep(_POLL_SECONDS)
            pids = [pid for pid in self._pids_within(root) if pid in pids]

        _signal(pids, signal.SIGKILL)

    def _pids_within(self, root: Path) -> list[int]:
        own_pid = os.getpid()

        return [
            pid
            for pid, working_dir in _working_dirs()
            if pid != own_pid and Path(working_dir).resolve().is_relative_to(root)
        ]


def _working_dirs() -> list[tuple[int, str]]:
    if _PROC_DIR.is_dir():
        return _proc_working_dirs()

    return _lsof_working_dirs()


def _proc_working_dirs() -> list[tuple[int, str]]:
    working_dirs = []
    for entry in _PROC_DIR.iterdir():
        if not entry.name.isdigit():
            continue

        try:
            working_dirs.append((int(entry.name), os.readlink(entry / "cwd")))
        except OSError:
            continue

    return working_dirs


def _lsof_working_dirs() -> list[tuple[int, str]]:
    try:
        listed = subprocess.run(
            ["lsof", "-w", "-d", "cwd", "-Fpn"],
            capture_output=True,
            text=True,
            timeout=_LIST_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"lsof failed: {error}") from error

    working_dirs = []
    pid: int | None = None
    for line in listed.stdout.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid is not None:
            working_dirs.append((pid, line[1:]))

    return working_dirs


def _signal(pids: list[int], signal_number: int) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal_number)
        except (ProcessLookupError, PermissionError):
            continue

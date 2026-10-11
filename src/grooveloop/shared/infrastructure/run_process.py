from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_ZOMBIE_STATE = "Z"
_POLL_SECONDS = 0.1


def is_run_process_alive(pid: int, run_dir: Path) -> bool:
    command_line = subprocess.run(
        ["ps", "-ww", "-o", "command=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    )

    return command_line.returncode == 0 and str(run_dir) in command_line.stdout


def stop_run_process_group(pid: int, grace_seconds: float) -> None:
    if not _signal_group(pid, signal.SIGTERM):
        return

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not _is_group_alive(pid):
            return

        time.sleep(_POLL_SECONDS)

    _signal_group(pid, signal.SIGKILL)


def _signal_group(pid: int, signal_number: int) -> bool:
    leader_signalled = _deliver(os.kill, pid, signal_number)
    group_signalled = _deliver(os.killpg, pid, signal_number)

    return leader_signalled or group_signalled


def _deliver(send: Callable[[int, int], None], pid: int, signal_number: int) -> bool:
    try:
        send(pid, signal_number)
    except (ProcessLookupError, PermissionError):
        return False

    return True


def _is_group_alive(pid: int) -> bool:
    processes = subprocess.run(
        ["ps", "-A", "-o", "pgid=", "-o", "stat="],
        check=False,
        capture_output=True,
        text=True,
    )

    return any(
        group == str(pid) and not state.startswith(_ZOMBIE_STATE)
        for group, state in (line.split() for line in processes.stdout.splitlines() if line.strip())
    )

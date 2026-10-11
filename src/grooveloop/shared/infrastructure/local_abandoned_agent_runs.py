from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from typing import TYPE_CHECKING

from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns
from grooveloop.shared.infrastructure.agent_exit_marker import read_exit_code, stalled_exit_lines, vanished_exit_lines
from grooveloop.shared.infrastructure.run_process import is_run_process_alive, stop_run_process_group

if TYPE_CHECKING:
    from pathlib import Path

    from grooveloop.shared.domain.clock import Clock

_METADATA_FILE = "run.json"
_LOG_FILE = "agent.log"
_STALL_AFTER = timedelta(minutes=30)
_KILL_GRACE_SECONDS = 10.0


class _Abandonment(Enum):
    VANISHED = auto()
    STALLED = auto()


class LocalAbandonedAgentRuns(AbandonedAgentRuns):
    def __init__(self, runs_dir: Path, clock: Clock) -> None:
        self._runs_dir = runs_dir
        self._clock = clock

    def abandoned_run_ids(self, repo: str) -> list[str]:
        if not self._runs_dir.is_dir():
            return []

        return [
            run_dir.name
            for run_dir in sorted(self._runs_dir.iterdir())
            if (metadata := _metadata_of(run_dir)) is not None
            and metadata.get("repo") == repo
            and (pid := _pid_of(metadata)) is not None
            and self._abandonment_of(run_dir, pid) is not None
        ]

    def close(self, run_id: str) -> None:
        run_dir = self._runs_dir / run_id
        metadata = _metadata_of(run_dir)
        pid = _pid_of(metadata) if metadata is not None else None
        if pid is None:
            return

        abandonment = self._abandonment_of(run_dir, pid)
        if abandonment is None:
            return

        log = run_dir / _LOG_FILE
        if abandonment is _Abandonment.VANISHED:
            _append_unless_exited(log, vanished_exit_lines())

            return

        stop_run_process_group(pid, _KILL_GRACE_SECONDS)
        _append_unless_exited(log, stalled_exit_lines())

    def _abandonment_of(self, run_dir: Path, pid: int) -> _Abandonment | None:
        log = run_dir / _LOG_FILE
        if not log.is_file() or read_exit_code(log) is not None:
            return None

        if not is_run_process_alive(pid, run_dir):
            return _Abandonment.VANISHED

        if self._clock.now() - datetime.fromtimestamp(log.stat().st_mtime, UTC) < _STALL_AFTER:
            return None

        return _Abandonment.STALLED


def _metadata_of(run_dir: Path) -> dict[str, object] | None:
    try:
        metadata = json.loads((run_dir / _METADATA_FILE).read_text())
    except (OSError, ValueError):
        return None

    return metadata if isinstance(metadata, dict) else None


def _pid_of(metadata: dict[str, object]) -> int | None:
    pid = metadata.get("pid")

    return pid if isinstance(pid, int) else None


def _append_unless_exited(log: Path, lines: str) -> None:
    if read_exit_code(log) is not None:
        return

    with log.open("a") as log_file:
        log_file.write(lines)

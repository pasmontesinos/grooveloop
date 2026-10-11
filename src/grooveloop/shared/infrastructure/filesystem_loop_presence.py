from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING

from grooveloop.shared.domain.loop_heartbeat import LoopHeartbeat
from grooveloop.shared.domain.loop_presence import LoopPresence

if TYPE_CHECKING:
    from pathlib import Path

    from grooveloop.shared.domain.clock import Clock

_HEARTBEAT_FILE = "heartbeat.json"
_PENDING_FILE = "heartbeat.json.tmp"
_HEARTBEAT_GLOB = f"*/*/{_HEARTBEAT_FILE}"


class FilesystemLoopPresence(LoopPresence):
    def __init__(self, repos_dir: Path, clock: Clock) -> None:
        self._repos_dir = repos_dir
        self._clock = clock

    def beat(self, repo: str) -> None:
        repo_dir = self._repos_dir / repo
        repo_dir.mkdir(parents=True, exist_ok=True)
        heartbeat = {"pid": os.getpid(), "repo": repo, "at": self._clock.now().isoformat()}

        pending = repo_dir / _PENDING_FILE
        pending.write_text(json.dumps(heartbeat))
        os.replace(pending, repo_dir / _HEARTBEAT_FILE)

    def heartbeats(self) -> list[LoopHeartbeat]:
        found = [self._read(path) for path in sorted(self._repos_dir.glob(_HEARTBEAT_GLOB))]

        return [heartbeat for heartbeat in found if heartbeat is not None]

    def _read(self, path: Path) -> LoopHeartbeat | None:
        try:
            stored = json.loads(path.read_text())
            heartbeat = LoopHeartbeat(
                repo=str(stored["repo"]),
                pid=int(stored["pid"]),
                at=datetime.fromisoformat(str(stored["at"])),
            )
        except (OSError, TypeError, ValueError, KeyError):
            return None

        if heartbeat.at.tzinfo is None:
            return None

        return heartbeat

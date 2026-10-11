from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from grooveloop.shared.domain.loop_presence import LoopPresence

if TYPE_CHECKING:
    from grooveloop.shared.domain.loop_heartbeat import LoopHeartbeat


class FakeLoopPresence(LoopPresence):
    def __init__(self, heartbeats: list[LoopHeartbeat] | None = None) -> None:
        self.beats: list[str] = []
        self._heartbeats = heartbeats if heartbeats is not None else []

    def beat(self, repo: str) -> None:
        self.beats.append(repo)

    def heartbeats(self) -> list[LoopHeartbeat]:
        return list(self._heartbeats)


class CountingLoopPresence(LoopPresence):
    def __init__(self, *, beats_awaited: int, failing: bool = False) -> None:
        self.awaited_beats_reached = threading.Event()
        self._beats = 0
        self._beats_awaited = beats_awaited
        self._failing = failing

    def beat(self, repo: str) -> None:
        self._beats += 1
        if self._beats >= self._beats_awaited:
            self.awaited_beats_reached.set()
        if self._failing:
            raise OSError("read-only file system")

    def heartbeats(self) -> list[LoopHeartbeat]:
        return []


class GatedLoopPresence(FakeLoopPresence):
    def __init__(self, heartbeats: list[LoopHeartbeat], gate_seconds: float) -> None:
        super().__init__(heartbeats)
        self.reads = 0
        self.in_flight = 0
        self.max_in_flight = 0
        self.held = threading.Event()
        self._gate = threading.Event()
        self._gate_seconds = gate_seconds
        self._lock = threading.Lock()

    def open(self) -> None:
        self._gate.set()

    def heartbeats(self) -> list[LoopHeartbeat]:
        with self._lock:
            self.reads += 1
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            gated = self.reads > 1
        if gated:
            self.held.set()
            self._gate.wait(self._gate_seconds)
        with self._lock:
            self.in_flight -= 1

        return super().heartbeats()

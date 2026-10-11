from __future__ import annotations

from grooveloop.shared.domain.process_liveness import ProcessLiveness


class FakeProcessLiveness(ProcessLiveness):
    def __init__(self, alive_pids: list[int] | None = None) -> None:
        self._alive_pids = alive_pids if alive_pids is not None else []

    def is_alive(self, pid: int) -> bool:
        return pid in self._alive_pids

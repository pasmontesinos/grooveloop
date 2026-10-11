from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.loop_heartbeat import LoopHeartbeat


class LoopPresence(ABC):
    @abstractmethod
    def beat(self, repo: str) -> None: ...

    @abstractmethod
    def heartbeats(self) -> list[LoopHeartbeat]: ...

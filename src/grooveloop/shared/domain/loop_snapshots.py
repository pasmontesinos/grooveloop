from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.loop_snapshot import LoopSnapshot


class LoopSnapshots(ABC):
    @abstractmethod
    def publish(self, snapshot: LoopSnapshot) -> None: ...

    @abstractmethod
    def find(self, repo: str) -> LoopSnapshot | None: ...

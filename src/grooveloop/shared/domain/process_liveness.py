from __future__ import annotations

from abc import ABC, abstractmethod


class ProcessLiveness(ABC):
    @abstractmethod
    def is_alive(self, pid: int) -> bool: ...

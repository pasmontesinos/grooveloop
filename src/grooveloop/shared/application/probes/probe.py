from __future__ import annotations

from abc import ABC, abstractmethod


class Probe(ABC):
    name: str

    @abstractmethod
    def check(self) -> None: ...

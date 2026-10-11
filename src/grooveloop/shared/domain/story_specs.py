from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.story_spec_reading import StorySpecReading


class StorySpecs(ABC):
    @abstractmethod
    def publish(self, repo: str, number: int, spec: str) -> None: ...

    @abstractmethod
    def find(self, repo: str, number: int) -> str | None: ...

    @abstractmethod
    def read(self, repo: str, number: int) -> StorySpecReading | None: ...

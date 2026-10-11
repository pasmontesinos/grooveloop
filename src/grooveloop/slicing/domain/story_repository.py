from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.slicing.domain.story import Story
    from grooveloop.slicing.domain.story_id import StoryId
    from grooveloop.slicing.domain.story_status import StoryStatus


class StoryRepository(ABC):
    @abstractmethod
    def find(self, id: StoryId) -> Story | None: ...

    @abstractmethod
    def save(self, story: Story) -> None: ...

    @abstractmethod
    def search(self, status: StoryStatus | None = None, open: bool | None = None) -> list[Story]: ...

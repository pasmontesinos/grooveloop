from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.slicing.domain.events import StoryReadyToSlice
from grooveloop.slicing.domain.story_status import StoryStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.slicing.domain.story_repository import StoryRepository


class StoryReadyToSliceDetector:
    def __init__(self, story_repository: StoryRepository) -> None:
        self._story_repository = story_repository

    def detect(self) -> Iterator[StoryReadyToSlice]:
        for story in self._story_repository.search(status=StoryStatus.READY_FOR_IMPLEMENTATION, open=True):
            if story.spec.items:
                yield StoryReadyToSlice(story_id=story.id)

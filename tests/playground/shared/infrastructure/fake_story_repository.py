from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.slicing.domain.story_repository import StoryRepository

if TYPE_CHECKING:
    from grooveloop.slicing.domain.story import Story
    from grooveloop.slicing.domain.story_id import StoryId
    from grooveloop.slicing.domain.story_status import StoryStatus


class FakeStoryRepository(StoryRepository):
    def __init__(self) -> None:
        self._stories: dict[StoryId, Story] = {}

    def find(self, id: StoryId) -> Story | None:
        return self._stories.get(id)

    def save(self, story: Story) -> None:
        self._stories[story.id] = story

    def search(self, status: StoryStatus | None = None, open: bool | None = None) -> list[Story]:
        stories = list(self._stories.values())

        if status is not None:
            stories = [story for story in stories if story.status == status]

        return stories

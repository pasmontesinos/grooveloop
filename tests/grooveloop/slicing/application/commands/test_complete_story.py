from __future__ import annotations

import pytest

from grooveloop.slicing.application.commands.complete_story import (
    CompleteStoryCommand,
    CompleteStoryCommandHandler,
)
from grooveloop.slicing.domain.exceptions import StoryNotFoundError, StoryNotSlicedError
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.domain.story_status import StoryStatus
from tests.grooveloop.slicing.mothers.story_mother import StoryMother
from tests.playground.shared.infrastructure.fake_story_repository import FakeStoryRepository


class TestCompleteStoryCommandHandler:
    def test_should_mark_the_story_done(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="story-1", status=StoryStatus.SLICED))
        handler = CompleteStoryCommandHandler(story_repository=repository)

        handler(CompleteStoryCommand(story_id="story-1"))

        stored = repository.find(StoryId("story-1"))
        assert stored is not None
        assert stored.status == StoryStatus.DONE

    def test_should_raise_when_story_not_found(self) -> None:
        handler = CompleteStoryCommandHandler(story_repository=FakeStoryRepository())

        with pytest.raises(StoryNotFoundError):
            handler(CompleteStoryCommand(story_id="missing"))

    def test_should_raise_when_story_is_not_sliced(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="story-1", status=StoryStatus.READY_FOR_IMPLEMENTATION))
        handler = CompleteStoryCommandHandler(story_repository=repository)

        with pytest.raises(StoryNotSlicedError):
            handler(CompleteStoryCommand(story_id="story-1"))

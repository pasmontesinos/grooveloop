from __future__ import annotations

from grooveloop.shared.application.queries.get_story_spec import GetStorySpecQuery
from grooveloop.slicing.application.queries.get_story_spec import GetStorySpecQueryHandler
from grooveloop.slicing.domain.spec import Spec
from grooveloop.slicing.domain.story import Story
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.domain.story_status import StoryStatus
from tests.playground.shared.infrastructure.fake_story_repository import FakeStoryRepository


class TestGetStorySpecQueryHandler:
    def test_should_return_the_spec_text_of_the_story(self) -> None:
        repository = FakeStoryRepository()
        repository.save(
            Story(
                id=StoryId("10"),
                spec=Spec(items=[], text="## Goal\ndo X"),
                status=StoryStatus.READY_FOR_IMPLEMENTATION,
                slices=[],
            )
        )
        handler = GetStorySpecQueryHandler(story_repository=repository)

        result = handler(GetStorySpecQuery(story_id="10"))

        assert result is not None
        assert result.spec_text == "## Goal\ndo X"

    def test_should_return_none_when_the_story_does_not_exist(self) -> None:
        handler = GetStorySpecQueryHandler(story_repository=FakeStoryRepository())

        assert handler(GetStorySpecQuery(story_id="404")) is None

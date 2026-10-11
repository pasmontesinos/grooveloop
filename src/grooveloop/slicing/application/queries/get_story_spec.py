from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.get_story_spec import GetStorySpecQuery, GetStorySpecQueryResult
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.slicing.domain.story_id import StoryId

if TYPE_CHECKING:
    from grooveloop.slicing.domain.story_repository import StoryRepository


class GetStorySpecQueryHandler(QueryHandler[GetStorySpecQuery, GetStorySpecQueryResult | None]):
    def __init__(self, story_repository: StoryRepository) -> None:
        self._story_repository = story_repository

    def __call__(self, query: GetStorySpecQuery) -> GetStorySpecQueryResult | None:
        story = self._story_repository.find(StoryId(query.story_id))
        if story is None:
            return None

        return GetStorySpecQueryResult(spec_text=story.spec.text)

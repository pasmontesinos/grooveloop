from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.shared.application.queries.story_pull_request_numbers import (
    StoryPullRequestNumbersQuery,
    StoryPullRequestNumbersQueryResult,
)

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice_repository import SliceRepository


class StoryPullRequestNumbersQueryHandler(
    QueryHandler[StoryPullRequestNumbersQuery, StoryPullRequestNumbersQueryResult]
):
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def __call__(self, query: StoryPullRequestNumbersQuery) -> StoryPullRequestNumbersQueryResult:
        slices = self._slice_repository.search(story_id=StoryId(query.story_id))
        numbers = [a_slice.pull_request_number.value for a_slice in slices if a_slice.pull_request_number is not None]

        return StoryPullRequestNumbersQueryResult(pull_request_numbers=numbers)

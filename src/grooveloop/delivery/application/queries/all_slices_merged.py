from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.application.queries.all_slices_merged import AllSlicesMergedQuery, AllSlicesMergedQueryResult
from grooveloop.shared.application.queries.query_handler import QueryHandler

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice_repository import SliceRepository


class AllSlicesMergedQueryHandler(QueryHandler[AllSlicesMergedQuery, AllSlicesMergedQueryResult]):
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def __call__(self, query: AllSlicesMergedQuery) -> AllSlicesMergedQueryResult:
        slices = self._slice_repository.search(story_id=StoryId(query.story_id))
        all_merged = bool(slices) and all(a_slice.is_merged() for a_slice in slices)

        return AllSlicesMergedQueryResult(all_merged=all_merged)

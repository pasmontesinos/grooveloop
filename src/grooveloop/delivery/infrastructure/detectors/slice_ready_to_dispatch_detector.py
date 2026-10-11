from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.application.queries.next_dispatchable_slices import NextDispatchableSlicesQuery
from grooveloop.delivery.domain.events import SliceReadyToDispatch
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.queries.pending_lessons import PendingLessonsQuery

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.delivery.domain.story_id import StoryId
    from grooveloop.shared.application.queries.query_bus import QueryBus


class SliceReadyToDispatchDetector:
    def __init__(self, slice_repository: SliceRepository, query_bus: QueryBus) -> None:
        self._slice_repository = slice_repository
        self._query_bus = query_bus

    def detect(self) -> Iterator[SliceReadyToDispatch]:
        for story_id, slices in self._slices_by_story().items():
            dispatchable_ids = self._dispatchable_ids(story_id)
            for a_slice in slices:
                if a_slice.id not in dispatchable_ids:
                    continue

                dependencies = a_slice.dependencies(slices) or []
                if self._has_unresolved_lesson(dependencies):
                    continue

                yield SliceReadyToDispatch(slice_id=a_slice.id)

    def _dispatchable_ids(self, story_id: StoryId) -> set[SliceId]:
        result = self._query_bus.ask(NextDispatchableSlicesQuery(story_id=story_id.value))

        return {SliceId(dto.id) for dto in result.slices}

    def _slices_by_story(self) -> dict[StoryId, list[Slice]]:
        grouped: dict[StoryId, list[Slice]] = {}

        for a_slice in self._slice_repository.search():
            if a_slice.story_id is not None:
                grouped.setdefault(a_slice.story_id, []).append(a_slice)

        return grouped

    def _has_unresolved_lesson(self, dependencies: list[Slice]) -> bool:
        numbers = [
            dependency.pull_request_number.value
            for dependency in dependencies
            if dependency.pull_request_number is not None
        ]
        if not numbers:
            return False

        result = self._query_bus.ask(PendingLessonsQuery(pull_request_numbers=numbers))

        return len(result.pending_lessons) > 0

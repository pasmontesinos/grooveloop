from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.all_slices_merged import AllSlicesMergedQuery
from grooveloop.shared.application.queries.pending_lessons import PendingLessonsQuery
from grooveloop.shared.application.queries.pending_verifications import PendingVerificationsQuery
from grooveloop.shared.application.queries.story_pull_request_numbers import StoryPullRequestNumbersQuery
from grooveloop.shared.application.queries.uncaptured_lessons import UncapturedLessonsQuery
from grooveloop.slicing.domain.events import StoryCompleted
from grooveloop.slicing.domain.story_status import StoryStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.shared.application.queries.query_bus import QueryBus
    from grooveloop.slicing.domain.story_repository import StoryRepository


class StoryCompletedDetector:
    def __init__(self, story_repository: StoryRepository, query_bus: QueryBus) -> None:
        self._story_repository = story_repository
        self._query_bus = query_bus

    def detect(self) -> Iterator[StoryCompleted]:
        for story in self._story_repository.search(status=StoryStatus.SLICED, open=True):
            result = self._query_bus.ask(AllSlicesMergedQuery(story_id=story.id.value))
            if not result.all_merged:
                continue

            if self._has_pending_verification(story.id.value):
                continue

            pull_request_numbers = self._pull_request_numbers(story.id.value)
            if self._has_unresolved_lesson(pull_request_numbers):
                continue

            if self._has_uncaptured_lesson(pull_request_numbers):
                continue

            yield StoryCompleted(story_id=story.id)

    def _pull_request_numbers(self, story_id: str) -> list[int]:
        return self._query_bus.ask(StoryPullRequestNumbersQuery(story_id=story_id)).pull_request_numbers

    def _has_pending_verification(self, story_id: str) -> bool:
        verifications = self._query_bus.ask(PendingVerificationsQuery(story_id=story_id))

        return len(verifications.slice_ids) > 0

    def _has_unresolved_lesson(self, pull_request_numbers: list[int]) -> bool:
        if not pull_request_numbers:
            return False

        lessons = self._query_bus.ask(PendingLessonsQuery(pull_request_numbers=pull_request_numbers))

        return len(lessons.pending_lessons) > 0

    def _has_uncaptured_lesson(self, pull_request_numbers: list[int]) -> bool:
        if not pull_request_numbers:
            return False

        uncaptured = self._query_bus.ask(UncapturedLessonsQuery(pull_request_numbers=pull_request_numbers))

        return len(uncaptured.pull_request_numbers) > 0

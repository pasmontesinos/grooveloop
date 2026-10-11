from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.shared.application.queries.uncaptured_lessons import (
    UncapturedLessonsQuery,
    UncapturedLessonsQueryResult,
)

if TYPE_CHECKING:
    from grooveloop.learning.domain.learn_signal import LearnSignal
    from grooveloop.learning.domain.lesson_repository import LessonRepository


class UncapturedLessonsQueryHandler(QueryHandler[UncapturedLessonsQuery, UncapturedLessonsQueryResult]):
    def __init__(self, learn_signal: LearnSignal, lesson_repository: LessonRepository) -> None:
        self._learn_signal = learn_signal
        self._lesson_repository = lesson_repository

    def __call__(self, query: UncapturedLessonsQuery) -> UncapturedLessonsQueryResult:
        merged = {source.value for source in self._learn_signal.merged_pull_requests()}
        uncaptured = [
            number for number in query.pull_request_numbers if number in merged and self._is_uncaptured(number)
        ]

        return UncapturedLessonsQueryResult(pull_request_numbers=uncaptured)

    def _is_uncaptured(self, number: int) -> bool:
        source_pull_request = SourcePullRequest(number)
        if self._lesson_repository.find_by_source_pull_request(source_pull_request) is not None:
            return False

        return len(self._learn_signal.comments_of(source_pull_request)) > 0

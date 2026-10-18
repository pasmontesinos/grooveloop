from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.application.queries.pending_lesson_dto_mapper import pending_lesson_dto_from_domain
from grooveloop.shared.application.queries.pending_lessons import PendingLessonsQuery, PendingLessonsQueryResult
from grooveloop.shared.application.queries.query_handler import QueryHandler

if TYPE_CHECKING:
    from grooveloop.learning.domain.conventions_pull_request_status import ConventionsPullRequestStatus
    from grooveloop.learning.domain.lesson import Lesson
    from grooveloop.learning.domain.lesson_repository import LessonRepository


class PendingLessonsQueryHandler(QueryHandler[PendingLessonsQuery, PendingLessonsQueryResult]):
    def __init__(
        self,
        lesson_repository: LessonRepository,
        conventions_pull_request_status: ConventionsPullRequestStatus,
    ) -> None:
        self._lesson_repository = lesson_repository
        self._conventions_pull_request_status = conventions_pull_request_status

    def __call__(self, query: PendingLessonsQuery) -> PendingLessonsQueryResult:
        lessons = self._lesson_repository.search()

        pending = [
            pending_lesson_dto_from_domain(lesson)
            for number in query.pull_request_numbers
            for lesson in lessons
            if lesson.source_pull_request.value == number
            and not lesson.is_resolved(self._is_conventions_pull_request_open(lesson))
        ]

        return PendingLessonsQueryResult(pending_lessons=pending)

    def _is_conventions_pull_request_open(self, lesson: Lesson) -> bool:
        conventions_pull_request = lesson.conventions_pull_request

        return conventions_pull_request is not None and self._conventions_pull_request_status.is_open(
            conventions_pull_request
        )

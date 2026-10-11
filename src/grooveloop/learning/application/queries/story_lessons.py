from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from grooveloop.learning.domain.story_id import StoryId
from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.shared.application.queries.query_result import QueryResult

if TYPE_CHECKING:
    from grooveloop.learning.domain.conventions_pull_request_status import ConventionsPullRequestStatus
    from grooveloop.learning.domain.lesson import Lesson
    from grooveloop.learning.domain.lesson_repository import LessonRepository


@dataclass(frozen=True)
class StoryLessonDTO:
    number: str | None
    source_pull_request_number: int
    status: str
    conventions_pull_request_number: int | None
    resolved: bool

    @classmethod
    def from_domain(cls, lesson: Lesson, resolved: bool) -> Self:
        conventions_pull_request = lesson.conventions_pull_request

        return cls(
            number=lesson.id.value if lesson.id is not None else None,
            source_pull_request_number=lesson.source_pull_request.value,
            status=lesson.status.value,
            conventions_pull_request_number=(
                conventions_pull_request.value if conventions_pull_request is not None else None
            ),
            resolved=resolved,
        )


@dataclass(frozen=True)
class StoryLessonsQueryResult(QueryResult):
    lessons: list[StoryLessonDTO]


@dataclass(frozen=True)
class StoryLessonsQuery(Query[StoryLessonsQueryResult]):
    story_id: str


class StoryLessonsQueryHandler(QueryHandler[StoryLessonsQuery, StoryLessonsQueryResult]):
    def __init__(
        self,
        lesson_repository: LessonRepository,
        conventions_pull_request_status: ConventionsPullRequestStatus,
    ) -> None:
        self._lesson_repository = lesson_repository
        self._conventions_pull_request_status = conventions_pull_request_status

    def __call__(self, query: StoryLessonsQuery) -> StoryLessonsQueryResult:
        lessons = self._lesson_repository.search(story_id=StoryId(query.story_id))

        return StoryLessonsQueryResult(
            lessons=[
                StoryLessonDTO.from_domain(lesson, lesson.is_resolved(self._is_conventions_pull_request_open(lesson)))
                for lesson in lessons
            ]
        )

    def _is_conventions_pull_request_open(self, lesson: Lesson) -> bool:
        conventions_pull_request = lesson.conventions_pull_request

        return conventions_pull_request is not None and self._conventions_pull_request_status.is_open(
            conventions_pull_request
        )

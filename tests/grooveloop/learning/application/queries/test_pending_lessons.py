from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.learning.application.queries.pending_lessons import PendingLessonsQueryHandler
from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.shared.application.queries.pending_lessons import PendingLessonsQuery
from tests.playground.shared.infrastructure.fake_conventions_pull_request_status import (
    FakeConventionsPullRequestStatus,
)
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository


def _lesson(
    source_pull_request: int,
    status: LessonStatus,
    conventions_pull_request: int | None = None,
    lesson_id: int | None = None,
) -> Lesson:
    return Lesson(
        id=LessonId(str(lesson_id if lesson_id is not None else source_pull_request + 1000)),
        source_pull_request=SourcePullRequest(source_pull_request),
        story_id=StoryId("10"),
        status=status,
        comments=[],
        conventions_pull_request=(
            ConventionsPullRequest(conventions_pull_request) if conventions_pull_request is not None else None
        ),
        open=True,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestPendingLessonsQueryHandler:
    def test_returns_the_subset_of_pull_requests_with_an_unresolved_lesson(self) -> None:
        repository = FakeLessonRepository(
            lessons=[
                _lesson(42, LessonStatus.IN_PROGRESS),
                _lesson(100, LessonStatus.IN_PROGRESS),
            ]
        )
        handler = PendingLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        result = handler(PendingLessonsQuery(pull_request_numbers=[42, 55, 100]))

        assert [lesson.pull_request_number for lesson in result.pending_lessons] == [42, 100]

    def test_a_pull_request_with_a_resolved_lesson_and_a_newer_unresolved_one_stays_pending(self) -> None:
        repository = FakeLessonRepository(
            lessons=[
                _lesson(42, LessonStatus.IN_PROGRESS, lesson_id=1002),
                _lesson(42, LessonStatus.LEARNED, conventions_pull_request=101, lesson_id=1001),
            ]
        )
        handler = PendingLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(open_pull_requests=set()),
        )

        result = handler(PendingLessonsQuery(pull_request_numbers=[42]))

        assert [lesson.pull_request_number for lesson in result.pending_lessons] == [42]

    def test_ignores_pull_requests_without_a_lesson(self) -> None:
        repository = FakeLessonRepository(lessons=[])
        handler = PendingLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        result = handler(PendingLessonsQuery(pull_request_numbers=[42, 55]))

        assert result.pending_lessons == []

    def test_leaves_the_conventions_pull_request_empty_while_the_scribe_is_evaluating(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.IN_PROGRESS)])
        handler = PendingLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        result = handler(PendingLessonsQuery(pull_request_numbers=[42]))

        assert result.pending_lessons[0].conventions_pull_request_number is None

    def test_a_learned_lesson_with_an_open_conventions_pull_request_stays_pending(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.LEARNED, conventions_pull_request=101)])
        handler = PendingLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(open_pull_requests={101}),
        )

        result = handler(PendingLessonsQuery(pull_request_numbers=[42]))

        assert result.pending_lessons[0].conventions_pull_request_number == 101

    def test_a_learned_lesson_with_a_resolved_conventions_pull_request_is_not_pending(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.LEARNED, conventions_pull_request=101)])
        handler = PendingLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(open_pull_requests=set()),
        )

        result = handler(PendingLessonsQuery(pull_request_numbers=[42]))

        assert result.pending_lessons == []

    def test_a_discarded_lesson_is_not_pending(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.DISCARDED)])
        handler = PendingLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        result = handler(PendingLessonsQuery(pull_request_numbers=[42]))

        assert result.pending_lessons == []

from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.learning.application.queries.story_lessons import (
    StoryLessonsQuery,
    StoryLessonsQueryHandler,
)
from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from tests.playground.shared.infrastructure.fake_conventions_pull_request_status import (
    FakeConventionsPullRequestStatus,
)
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository


def _lesson(
    source_pull_request: int,
    status: LessonStatus,
    story: str = "10",
    conventions_pull_request: int | None = None,
) -> Lesson:
    return Lesson(
        id=LessonId(str(source_pull_request + 1000)),
        source_pull_request=SourcePullRequest(source_pull_request),
        story_id=StoryId(story),
        status=status,
        comments=[],
        conventions_pull_request=(
            ConventionsPullRequest(conventions_pull_request) if conventions_pull_request is not None else None
        ),
        open=True,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestStoryLessonsQueryHandler:
    def test_returns_the_captured_lessons_of_the_story(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.IN_PROGRESS)])
        handler = StoryLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        result = handler(StoryLessonsQuery(story_id="10"))

        assert [
            (lesson.number, lesson.source_pull_request_number, lesson.status, lesson.resolved)
            for lesson in result.lessons
        ] == [("1042", 42, "in_progress", False)]

    def test_excludes_the_lessons_of_another_story(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.IN_PROGRESS, story="20")])
        handler = StoryLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        result = handler(StoryLessonsQuery(story_id="10"))

        assert result.lessons == []

    def test_marks_as_pending_a_learned_lesson_whose_conventions_pull_request_is_open(self) -> None:
        repository = FakeLessonRepository(
            lessons=[_lesson(42, LessonStatus.LEARNED, conventions_pull_request=101)],
        )
        handler = StoryLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(open_pull_requests={101}),
        )

        result = handler(StoryLessonsQuery(story_id="10"))

        assert [
            (lesson.status, lesson.conventions_pull_request_number, lesson.resolved) for lesson in result.lessons
        ] == [("learned", 101, False)]

    def test_marks_as_resolved_a_learned_lesson_whose_conventions_pull_request_is_closed(self) -> None:
        repository = FakeLessonRepository(
            lessons=[_lesson(42, LessonStatus.LEARNED, conventions_pull_request=101)],
        )
        handler = StoryLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(open_pull_requests=set()),
        )

        result = handler(StoryLessonsQuery(story_id="10"))

        assert [(lesson.status, lesson.resolved) for lesson in result.lessons] == [("learned", True)]

    def test_marks_as_resolved_a_discarded_lesson(self) -> None:
        repository = FakeLessonRepository(lessons=[_lesson(42, LessonStatus.DISCARDED)])
        handler = StoryLessonsQueryHandler(
            lesson_repository=repository,
            conventions_pull_request_status=FakeConventionsPullRequestStatus(),
        )

        result = handler(StoryLessonsQuery(story_id="10"))

        assert [(lesson.status, lesson.resolved) for lesson in result.lessons] == [("discarded", True)]

from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.learning.application.commands.close_lesson import CloseLessonCommand, CloseLessonCommandHandler
from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from tests.grooveloop.learning.mothers.lesson_mother import LessonMother
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository


def _in_progress(number: int) -> Lesson:
    return LessonMother.create(source_pull_request=number, story_id="10")


def _closed(id: str, number: int) -> Lesson:
    return Lesson(
        id=LessonId(id),
        source_pull_request=SourcePullRequest(number),
        story_id=StoryId("10"),
        status=LessonStatus.DISCARDED,
        comments=[],
        conventions_pull_request=None,
        open=False,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestCloseLessonCommandHandler:
    def test_closes_the_sub_issue_of_an_open_lesson(self) -> None:
        repository = FakeLessonRepository()
        repository.save(_in_progress(42))
        handler = CloseLessonCommandHandler(lesson_repository=repository)

        handler(CloseLessonCommand(lesson_id="1000"))

        stored = repository.find(LessonId("1000"))
        assert stored is not None
        assert stored.is_open is False

    def test_is_idempotent_when_the_lesson_is_already_closed(self) -> None:
        repository = FakeLessonRepository(lessons=[_closed("500", 42)])
        handler = CloseLessonCommandHandler(lesson_repository=repository)

        handler(CloseLessonCommand(lesson_id="500"))

        assert repository.saved == []

    def test_does_nothing_when_no_lesson_exists(self) -> None:
        repository = FakeLessonRepository()
        handler = CloseLessonCommandHandler(lesson_repository=repository)

        handler(CloseLessonCommand(lesson_id="500"))

        assert repository.saved == []

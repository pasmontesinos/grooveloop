from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.application.commands.discard_lesson import DiscardLessonCommand, DiscardLessonCommandHandler
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from tests.grooveloop.learning.mothers.lesson_mother import LessonMother
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson import Lesson


def _in_progress(number: int) -> Lesson:
    return LessonMother.create(source_pull_request=number, story_id="10")


class TestDiscardLessonCommandHandler:
    def test_moves_the_lesson_to_discarded_without_conventions_pull_request(self) -> None:
        repository = FakeLessonRepository()
        repository.save(_in_progress(42))
        handler = DiscardLessonCommandHandler(lesson_repository=repository)

        handler(DiscardLessonCommand(source_pull_request=42))

        stored = repository.find_by_source_pull_request(SourcePullRequest(42))
        assert stored is not None
        assert stored.status == LessonStatus.DISCARDED
        assert stored.conventions_pull_request is None

    def test_is_idempotent_when_the_lesson_is_already_terminal(self) -> None:
        repository = FakeLessonRepository()
        repository.save(_in_progress(42))
        handler = DiscardLessonCommandHandler(lesson_repository=repository)
        handler(DiscardLessonCommand(source_pull_request=42))
        saved_count = len(repository.saved)

        handler(DiscardLessonCommand(source_pull_request=42))

        assert len(repository.saved) == saved_count

    def test_does_nothing_when_no_lesson_exists_for_the_pull_request(self) -> None:
        repository = FakeLessonRepository()
        handler = DiscardLessonCommandHandler(lesson_repository=repository)

        handler(DiscardLessonCommand(source_pull_request=42))

        assert repository.saved == []

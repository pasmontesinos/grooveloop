from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.application.commands.learn_lesson import LearnLessonCommand, LearnLessonCommandHandler
from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_status import LessonStatus
from tests.grooveloop.learning.mothers.lesson_mother import LessonMother
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson import Lesson


def _in_progress(number: int) -> Lesson:
    return LessonMother.create(lesson_id="500", source_pull_request=number, story_id="10")


class TestLearnLessonCommandHandler:
    def test_moves_the_lesson_to_learned_with_the_conventions_pull_request(self) -> None:
        repository = FakeLessonRepository(lessons=[_in_progress(42)])
        handler = LearnLessonCommandHandler(lesson_repository=repository)

        handler(LearnLessonCommand(source_pull_request=42, conventions_pull_request=99))

        stored = repository.find(LessonId("500"))
        assert stored is not None
        assert stored.status == LessonStatus.LEARNED
        assert stored.conventions_pull_request == ConventionsPullRequest(99)

    def test_is_idempotent_when_the_lesson_is_already_terminal(self) -> None:
        repository = FakeLessonRepository(lessons=[_in_progress(42)])
        handler = LearnLessonCommandHandler(lesson_repository=repository)
        handler(LearnLessonCommand(source_pull_request=42, conventions_pull_request=99))

        handler(LearnLessonCommand(source_pull_request=42, conventions_pull_request=123))

        stored = repository.find(LessonId("500"))
        assert stored is not None
        assert stored.conventions_pull_request == ConventionsPullRequest(99)

    def test_does_nothing_when_no_lesson_exists_for_the_pull_request(self) -> None:
        repository = FakeLessonRepository()
        handler = LearnLessonCommandHandler(lesson_repository=repository)

        handler(LearnLessonCommand(source_pull_request=42, conventions_pull_request=99))

        assert repository.saved == []

    def test_learns_the_lesson_in_progress_and_leaves_an_earlier_lesson_of_the_pull_request_untouched(self) -> None:
        earlier = LessonMother.create(
            lesson_id="400",
            source_pull_request=42,
            status=LessonStatus.LEARNED,
            conventions_pull_request=ConventionsPullRequest(99),
        )
        repository = FakeLessonRepository(lessons=[earlier, _in_progress(42)])
        handler = LearnLessonCommandHandler(lesson_repository=repository)

        handler(LearnLessonCommand(source_pull_request=42, conventions_pull_request=123))

        stored = repository.find(LessonId("500"))
        assert stored is not None
        assert stored.status == LessonStatus.LEARNED
        assert stored.conventions_pull_request == ConventionsPullRequest(123)
        assert [lesson.id for lesson in repository.saved] == [LessonId("500")]

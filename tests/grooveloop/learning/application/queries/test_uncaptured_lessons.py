from __future__ import annotations

from grooveloop.learning.application.queries.uncaptured_lessons import UncapturedLessonsQueryHandler
from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.shared.application.queries.uncaptured_lessons import UncapturedLessonsQuery
from tests.playground.shared.infrastructure.fake_learn_signal import FakeLearnSignal
from tests.playground.shared.infrastructure.fake_lesson_repository import FakeLessonRepository


def _learn_comment() -> LessonComment:
    return LessonComment(body="/grooveloop-learn something", path="src/x.py", line=10, diff_hunk="@@ @@")


def _lesson(source_pull_request: int) -> Lesson:
    return Lesson(
        id=LessonId(str(source_pull_request + 1000)),
        source_pull_request=SourcePullRequest(source_pull_request),
        story_id=StoryId("10"),
        status=LessonStatus.IN_PROGRESS,
        comments=[],
        conventions_pull_request=None,
        open=True,
    )


class TestUncapturedLessonsQueryHandler:
    def test_returns_the_pull_requests_with_a_learn_directive_and_no_lesson(self) -> None:
        handler = UncapturedLessonsQueryHandler(
            learn_signal=FakeLearnSignal(comments={42: [_learn_comment()], 55: []}),
            lesson_repository=FakeLessonRepository(),
        )

        result = handler(UncapturedLessonsQuery(pull_request_numbers=[42, 55]))

        assert result.pull_request_numbers == [42]

    def test_ignores_a_pull_request_whose_lesson_already_exists(self) -> None:
        handler = UncapturedLessonsQueryHandler(
            learn_signal=FakeLearnSignal(comments={42: [_learn_comment()]}),
            lesson_repository=FakeLessonRepository(lessons=[_lesson(42)]),
        )

        result = handler(UncapturedLessonsQuery(pull_request_numbers=[42]))

        assert result.pull_request_numbers == []

    def test_ignores_a_pull_request_that_is_not_merged(self) -> None:
        handler = UncapturedLessonsQueryHandler(
            learn_signal=FakeLearnSignal(comments={42: [_learn_comment()]}),
            lesson_repository=FakeLessonRepository(),
        )

        result = handler(UncapturedLessonsQuery(pull_request_numbers=[99]))

        assert result.pull_request_numbers == []

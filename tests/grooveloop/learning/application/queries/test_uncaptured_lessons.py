from __future__ import annotations

from grooveloop.learning.application.queries.uncaptured_lessons import UncapturedLessonsQueryHandler
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.shared.application.queries.uncaptured_lessons import UncapturedLessonsQuery
from tests.playground.shared.infrastructure.fake_learn_signal import FakeLearnSignal


def _learn_comment(captured: bool = False) -> LessonComment:
    return LessonComment(
        body="/grooveloop-learn something",
        path="src/x.py",
        line=10,
        diff_hunk="@@ @@",
        id=None,
        captured=captured,
    )


class TestUncapturedLessonsQueryHandler:
    def test_returns_the_pull_requests_with_a_learn_directive_not_marked_by_the_loop(self) -> None:
        handler = UncapturedLessonsQueryHandler(
            learn_signal=FakeLearnSignal(comments={42: [_learn_comment()], 55: []}),
        )

        result = handler(UncapturedLessonsQuery(pull_request_numbers=[42, 55]))

        assert result.pull_request_numbers == [42]

    def test_ignores_a_pull_request_whose_learn_comments_are_all_marked_by_the_loop(self) -> None:
        handler = UncapturedLessonsQueryHandler(
            learn_signal=FakeLearnSignal(comments={42: [_learn_comment(captured=True)]}),
        )

        result = handler(UncapturedLessonsQuery(pull_request_numbers=[42]))

        assert result.pull_request_numbers == []

    def test_ignores_a_pull_request_that_is_not_merged(self) -> None:
        handler = UncapturedLessonsQueryHandler(
            learn_signal=FakeLearnSignal(comments={42: [_learn_comment()]}),
        )

        result = handler(UncapturedLessonsQuery(pull_request_numbers=[99]))

        assert result.pull_request_numbers == []

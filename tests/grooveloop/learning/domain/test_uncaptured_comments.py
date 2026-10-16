from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.uncaptured_comments import uncaptured_comments
from tests.grooveloop.learning.mothers.lesson_mother import LessonMother

_FIRST_CAPTURE = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)
_SECOND_CAPTURE = datetime(2026, 10, 16, 14, 0, tzinfo=UTC)


def _learn_comment(id: str, hour: int, captured: bool = False) -> LessonComment:
    return LessonComment(
        body=f"/grooveloop-learn: {id}",
        path="",
        line=0,
        diff_hunk="",
        id=id,
        written_at=datetime(2026, 10, 16, hour, 0, tzinfo=UTC),
        captured=captured,
    )


class TestUncapturedComments:
    def test_every_learn_comment_is_uncaptured_on_a_pull_request_without_lessons(self) -> None:
        comments = [_learn_comment("a", 9), _learn_comment("b", 11)]

        assert uncaptured_comments(comments, []) == comments

    def test_the_learn_comments_written_before_the_lesson_of_an_unmarked_pull_request_count_as_captured(self) -> None:
        lesson = LessonMother.create(status=LessonStatus.LEARNED, captured_at=_FIRST_CAPTURE)

        assert uncaptured_comments([_learn_comment("a", 8), _learn_comment("b", 9)], [lesson]) == []

    def test_a_learn_comment_written_after_the_lesson_is_uncaptured(self) -> None:
        lesson = LessonMother.create(status=LessonStatus.LEARNED, captured_at=_FIRST_CAPTURE)
        later = _learn_comment("b", 12)

        assert uncaptured_comments([_learn_comment("a", 9), later], [lesson]) == [later]

    def test_a_learn_comment_marked_by_the_loop_is_captured_whenever_it_was_written(self) -> None:
        first = LessonMother.create(lesson_id="500", status=LessonStatus.LEARNED, captured_at=_FIRST_CAPTURE)
        second = LessonMother.create(lesson_id="501", status=LessonStatus.LEARNED, captured_at=_SECOND_CAPTURE)
        pending = _learn_comment("c", 13)

        result = uncaptured_comments(
            [_learn_comment("a", 9), _learn_comment("b", 12, captured=True), pending], [second, first]
        )

        assert result == [pending]

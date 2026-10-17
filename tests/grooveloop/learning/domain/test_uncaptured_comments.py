from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.uncaptured_comments import uncaptured_comments


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
    def test_every_learn_comment_without_the_mark_of_the_loop_is_uncaptured(self) -> None:
        comments = [_learn_comment("a", 9), _learn_comment("b", 11)]

        assert uncaptured_comments(comments) == comments

    def test_a_learn_comment_marked_by_the_loop_is_captured(self) -> None:
        pending = _learn_comment("c", 13)

        assert uncaptured_comments([_learn_comment("a", 9, captured=True), pending]) == [pending]

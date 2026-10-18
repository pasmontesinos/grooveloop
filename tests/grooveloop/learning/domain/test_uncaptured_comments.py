from __future__ import annotations

from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.uncaptured_comments import uncaptured_comments


def _learn_comment(id: str, captured: bool = False) -> LessonComment:
    return LessonComment(
        body=f"/grooveloop-learn: {id}",
        path="",
        line=0,
        diff_hunk="",
        id=id,
        captured=captured,
    )


class TestUncapturedComments:
    def test_every_learn_comment_without_the_mark_of_the_loop_is_uncaptured(self) -> None:
        comments = [_learn_comment("a"), _learn_comment("b")]

        assert uncaptured_comments(comments) == comments

    def test_a_learn_comment_marked_by_the_loop_is_captured(self) -> None:
        pending = _learn_comment("c")

        assert uncaptured_comments([_learn_comment("a", captured=True), pending]) == [pending]

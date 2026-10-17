from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_comment import LessonComment


def uncaptured_comments(comments: list[LessonComment]) -> list[LessonComment]:
    return [comment for comment in comments if not comment.captured]

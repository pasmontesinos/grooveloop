from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson import Lesson
    from grooveloop.learning.domain.lesson_comment import LessonComment


def uncaptured_comments(comments: list[LessonComment], lessons: list[Lesson]) -> list[LessonComment]:
    if any(comment.captured for comment in comments):
        return [comment for comment in comments if not comment.captured]

    if not lessons:
        return list(comments)

    first_capture = min(lesson.captured_at for lesson in lessons)

    return [comment for comment in comments if comment.written_at >= first_capture]

from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.lesson_repository import LessonRepository

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_status import LessonStatus
    from grooveloop.learning.domain.source_pull_request import SourcePullRequest
    from grooveloop.learning.domain.story_id import StoryId


class FakeLessonRepository(LessonRepository):
    def __init__(self, lessons: list[Lesson] | None = None) -> None:
        self._lessons: list[Lesson] = list(lessons or [])
        self._next_number = 1000
        self.saved: list[Lesson] = []

    def find(self, id: LessonId) -> Lesson | None:
        return next((lesson for lesson in self._lessons if lesson.id == id), None)

    def find_by_source_pull_request(self, source_pull_request: SourcePullRequest) -> Lesson | None:
        return next((lesson for lesson in self._lessons if lesson.source_pull_request == source_pull_request), None)

    def save(self, lesson: Lesson) -> None:
        stored = lesson
        if lesson.id is None:
            stored = Lesson(
                id=LessonId(str(self._next_number)),
                source_pull_request=lesson.source_pull_request,
                story_id=lesson.story_id,
                status=lesson.status,
                comments=lesson.comments,
                conventions_pull_request=lesson.conventions_pull_request,
                open=lesson.is_open,
            )
            self._next_number += 1

        self._lessons = [existing for existing in self._lessons if existing.id != stored.id]
        self._lessons.append(stored)
        self.saved.append(stored)

    def search(self, status: LessonStatus | None = None, story_id: StoryId | None = None) -> list[Lesson]:
        return [
            lesson
            for lesson in self._lessons
            if (status is None or lesson.status == status) and (story_id is None or lesson.story_id == story_id)
        ]

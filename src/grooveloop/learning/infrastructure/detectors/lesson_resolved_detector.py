from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.events import LessonResolved

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.learning.domain.conventions_pull_request_status import ConventionsPullRequestStatus
    from grooveloop.learning.domain.lesson import Lesson
    from grooveloop.learning.domain.lesson_repository import LessonRepository


class LessonResolvedDetector:
    def __init__(
        self,
        lesson_repository: LessonRepository,
        conventions_pull_request_status: ConventionsPullRequestStatus,
    ) -> None:
        self._lesson_repository = lesson_repository
        self._conventions_pull_request_status = conventions_pull_request_status

    def detect(self) -> Iterator[LessonResolved]:
        for lesson in self._lesson_repository.search():
            story_id = lesson.story_id
            if lesson.id is None or story_id is None or not lesson.is_open:
                continue

            if lesson.is_resolved(self._is_conventions_pull_request_open(lesson)):
                yield LessonResolved(lesson_id=lesson.id, story_id=story_id)

    def _is_conventions_pull_request_open(self, lesson: Lesson) -> bool:
        conventions_pull_request = lesson.conventions_pull_request

        return conventions_pull_request is not None and self._conventions_pull_request_status.is_open(
            conventions_pull_request
        )

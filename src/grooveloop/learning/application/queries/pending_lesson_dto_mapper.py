from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.pending_lessons import PendingLessonDTO

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson import Lesson


def pending_lesson_dto_from_domain(lesson: Lesson) -> PendingLessonDTO:
    conventions_pull_request = lesson.conventions_pull_request

    return PendingLessonDTO(
        pull_request_number=lesson.source_pull_request.value,
        conventions_pull_request_number=(
            conventions_pull_request.value if conventions_pull_request is not None else None
        ),
    )

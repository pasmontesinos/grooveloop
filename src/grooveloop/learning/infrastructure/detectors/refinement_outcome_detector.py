from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.events import LessonDiscarded, LessonLearned
from grooveloop.learning.domain.lesson_status import LessonStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.learning.domain.lesson_repository import LessonRepository
    from grooveloop.learning.domain.refinement_result import RefinementResult
    from grooveloop.shared.domain.event import Event


class RefinementOutcomeDetector:
    def __init__(self, refinement_result: RefinementResult, lesson_repository: LessonRepository) -> None:
        self._refinement_result = refinement_result
        self._lesson_repository = lesson_repository

    def detect(self) -> Iterator[Event]:
        for lesson in self._lesson_repository.search(status=LessonStatus.IN_PROGRESS):
            story_id = lesson.story_id
            if story_id is None:
                continue

            outcome = self._refinement_result.of(lesson.source_pull_request, lesson.captured_at)
            if outcome is None:
                continue

            if outcome.conventions_pull_request is not None:
                yield LessonLearned(
                    source_pull_request=lesson.source_pull_request,
                    story_id=story_id,
                    conventions_pull_request=outcome.conventions_pull_request,
                )
            elif outcome.discarded:
                yield LessonDiscarded(source_pull_request=lesson.source_pull_request, story_id=story_id)

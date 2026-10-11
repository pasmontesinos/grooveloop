from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.events import LessonCaptured

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.learning.domain.learn_signal import LearnSignal
    from grooveloop.learning.domain.lesson_repository import LessonRepository


class LessonCapturedDetector:
    def __init__(self, learn_signal: LearnSignal, lesson_repository: LessonRepository) -> None:
        self._learn_signal = learn_signal
        self._lesson_repository = lesson_repository

    def detect(self) -> Iterator[LessonCaptured]:
        for source_pull_request in self._learn_signal.merged_pull_requests():
            if self._lesson_repository.find_by_source_pull_request(source_pull_request) is not None:
                continue

            comments = self._learn_signal.comments_of(source_pull_request)
            if not comments:
                continue

            yield LessonCaptured(
                source_pull_request=source_pull_request,
                story_id=self._learn_signal.story_of(source_pull_request),
                comments=comments,
            )

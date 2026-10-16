from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson import Lesson
    from grooveloop.learning.domain.lesson_id import LessonId
    from grooveloop.learning.domain.lesson_status import LessonStatus
    from grooveloop.learning.domain.source_pull_request import SourcePullRequest
    from grooveloop.learning.domain.story_id import StoryId


class LessonRepository(ABC):
    @abstractmethod
    def find(self, id: LessonId) -> Lesson | None: ...

    @abstractmethod
    def save(self, lesson: Lesson) -> None: ...

    @abstractmethod
    def search(
        self,
        status: LessonStatus | None = None,
        story_id: StoryId | None = None,
        source_pull_request: SourcePullRequest | None = None,
    ) -> list[Lesson]: ...

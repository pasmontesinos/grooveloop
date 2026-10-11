from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_comment import LessonComment
    from grooveloop.learning.domain.source_pull_request import SourcePullRequest
    from grooveloop.learning.domain.story_id import StoryId


class LearnSignal(ABC):
    @abstractmethod
    def merged_pull_requests(self) -> list[SourcePullRequest]: ...

    @abstractmethod
    def story_of(self, source_pull_request: SourcePullRequest) -> StoryId: ...

    @abstractmethod
    def comments_of(self, source_pull_request: SourcePullRequest) -> list[LessonComment]: ...

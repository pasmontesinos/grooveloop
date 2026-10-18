from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_comment import LessonComment


class LessonCommentMarker(ABC):
    @abstractmethod
    def mark_captured(self, comments: list[LessonComment]) -> None: ...

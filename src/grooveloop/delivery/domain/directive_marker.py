from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.domain.directive_mark import DirectiveMark
    from grooveloop.delivery.domain.review_comment import ReviewComment


class DirectiveMarker(ABC):
    @abstractmethod
    def mark(self, directives: list[ReviewComment], mark: DirectiveMark) -> None: ...

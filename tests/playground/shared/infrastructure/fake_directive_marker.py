from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.delivery.domain.directive_marker import DirectiveMarker

if TYPE_CHECKING:
    from grooveloop.delivery.domain.review_comment import ReviewComment


class FakeDirectiveMarker(DirectiveMarker):
    def __init__(self) -> None:
        self.marked: dict[DirectiveMark, list[ReviewComment]] = {mark: [] for mark in DirectiveMark}
        self.calls: list[DirectiveMark] = []

    def mark(self, directives: list[ReviewComment], mark: DirectiveMark) -> None:
        self.marked[mark].extend(directives)
        self.calls.append(mark)

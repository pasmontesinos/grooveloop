from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.shared.domain.comment_directive import CommentDirective

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class ReviewComment:
    body: str
    created_at: datetime
    path: str | None = None
    line: int | None = None
    thread_id: str | None = None
    directives: frozenset[CommentDirective] = frozenset()
    id: str | None = None
    marks: frozenset[DirectiveMark] = frozenset()
    taken_at: datetime | None = None

    def requests_implementation(self) -> bool:
        return CommentDirective.IMPLEMENT in self.directives

    def is_marked(self) -> bool:
        return len(self.marks) > 0

    def is_taken(self) -> bool:
        return DirectiveMark.TAKEN in self.marks and not self.is_addressed()

    def is_addressed(self) -> bool:
        return DirectiveMark.ADDRESSED in self.marks

    def reviewed_at(self) -> datetime:
        return self.taken_at if self.taken_at is not None else self.created_at

    def only_requests_learning(self) -> bool:
        return self.directives == frozenset({CommentDirective.LEARN})

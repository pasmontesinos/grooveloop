from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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

    def requests_implementation(self) -> bool:
        return CommentDirective.IMPLEMENT in self.directives

    def only_requests_learning(self) -> bool:
        return self.directives == frozenset({CommentDirective.LEARN})

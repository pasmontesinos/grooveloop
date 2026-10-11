from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class PullRequestComment:
    author: str | None
    body: str
    created_at: datetime
    path: str | None = None
    line: int | None = None
    diff_hunk: str | None = None

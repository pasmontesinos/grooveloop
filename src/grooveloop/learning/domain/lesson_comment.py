from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class LessonComment:
    body: str
    path: str
    line: int
    diff_hunk: str
    id: str | None
    written_at: datetime
    captured: bool = False

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LessonComment:
    body: str
    path: str
    line: int
    diff_hunk: str

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SliceSpecItem:
    title: str
    order: int
    body: str = ""
    depends_on: list[int] | None = None

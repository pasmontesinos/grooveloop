from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolTally:
    name: str
    count: int

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StorySpecReading:
    spec: str
    mtime_ns: int

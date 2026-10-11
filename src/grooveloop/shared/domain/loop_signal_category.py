from __future__ import annotations

from enum import StrEnum


class LoopSignalCategory(StrEnum):
    BROKEN = "broken"
    WAITING = "waiting"

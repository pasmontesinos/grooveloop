from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnGrowth:
    turn: int
    added_tokens: int
    after_action: str | None = None

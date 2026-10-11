from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoopRun:
    slice_number: str
    running: bool
    elapsed_seconds: float
    cost_usd: float
    silent_seconds: float

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.shared.domain.tick_outcome import TickOutcome


@dataclass(frozen=True)
class SnapshotTick:
    outcome: TickOutcome
    at: datetime
    duration_seconds: int
    interval_seconds: int

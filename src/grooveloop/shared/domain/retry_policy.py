from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

_FIRST_WAIT = timedelta(minutes=2)
_WAIT_GROWTH = 4


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int

    def has_budget(self, retries: int) -> bool:
        return retries < self.max_retries

    def is_due(self, retries: int, finished_at: datetime, now: datetime) -> bool:
        return now >= finished_at + _FIRST_WAIT * int(_WAIT_GROWTH**retries)

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

from grooveloop.shared.domain.clock import Clock

if TYPE_CHECKING:
    from datetime import datetime


def clock_at(now: datetime) -> Any:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = now

    return clock

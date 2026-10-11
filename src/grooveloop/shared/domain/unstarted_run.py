from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

_UNSTARTED_AFTER = timedelta(minutes=5)


def is_unstarted(has_log: bool, started_at: datetime, now: datetime) -> bool:
    return not has_log and now - started_at > _UNSTARTED_AFTER

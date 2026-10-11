from __future__ import annotations

from enum import Enum


class ReviewVerdict(Enum):
    EMPTY = None
    APPROVE = "approve"
    MINOR = "minor"
    BLOCKING = "blocking"
    BLOCKED = "blocked"

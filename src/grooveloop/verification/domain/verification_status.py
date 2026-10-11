from __future__ import annotations

from enum import Enum


class VerificationStatus(Enum):
    EMPTY = None
    RUNNING = "running"
    CONCLUDED = "concluded"
    FAILED = "failed"

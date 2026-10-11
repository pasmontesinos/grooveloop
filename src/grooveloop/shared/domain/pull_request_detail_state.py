from __future__ import annotations

from enum import StrEnum


class PullRequestDetailState(StrEnum):
    MISSING = "missing"
    UNREADABLE = "unreadable"
    SYNCED = "synced"

from __future__ import annotations

from enum import StrEnum


class SnapshotMergeability(StrEnum):
    MERGEABLE = "mergeable"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"

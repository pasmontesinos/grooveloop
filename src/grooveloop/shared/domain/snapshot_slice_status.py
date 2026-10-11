from __future__ import annotations

from enum import StrEnum


class SnapshotSliceStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    UNDER_REVIEW = "under_review"
    PR_OPEN = "pr_open"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"
    MERGED = "merged"
    FAILED = "failed"

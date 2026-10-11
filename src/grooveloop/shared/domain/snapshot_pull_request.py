from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.shared.domain.snapshot_mergeability import SnapshotMergeability


@dataclass(frozen=True)
class SnapshotPullRequest:
    title: str
    additions: int
    deletions: int
    changed_files: int
    updated_at: datetime
    head_ref_oid: str
    mergeable: SnapshotMergeability
    checks: str | None

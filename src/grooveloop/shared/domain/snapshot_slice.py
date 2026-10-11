from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.snapshot_pull_request import SnapshotPullRequest
    from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus


@dataclass(frozen=True)
class SnapshotSlice:
    number: str
    status: SnapshotSliceStatus
    title: str
    pr_number: str | None
    depends_on: list[str] = field(default_factory=list)
    pull_request: SnapshotPullRequest | None = None

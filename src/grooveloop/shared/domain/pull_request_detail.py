from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.shared.domain.pull_request_comment import PullRequestComment
    from grooveloop.shared.domain.pull_request_file import PullRequestFile


@dataclass(frozen=True)
class PullRequestDetail:
    number: int
    body: str
    updated_at: datetime
    head_ref_oid: str
    checks: str | None
    synced_at: datetime
    files: list[PullRequestFile]
    conversation: list[PullRequestComment]
    review: list[PullRequestComment]

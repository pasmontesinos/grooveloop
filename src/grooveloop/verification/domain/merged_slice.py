from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.verification.domain.pull_request_number import PullRequestNumber
    from grooveloop.verification.domain.slice_id import SliceId


@dataclass(frozen=True)
class MergedSlice:
    slice_id: SliceId
    pull_request_number: PullRequestNumber
    title: str
    description: str
    has_report: bool

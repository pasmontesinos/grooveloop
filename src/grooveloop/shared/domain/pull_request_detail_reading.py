from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.pull_request_detail import PullRequestDetail
    from grooveloop.shared.domain.pull_request_detail_state import PullRequestDetailState


@dataclass(frozen=True)
class PullRequestDetailReading:
    state: PullRequestDetailState
    detail: PullRequestDetail | None = None

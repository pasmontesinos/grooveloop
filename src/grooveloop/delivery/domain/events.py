from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.domain.event import Event

if TYPE_CHECKING:
    from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
    from grooveloop.delivery.domain.slice_id import SliceId


@dataclass(frozen=True)
class PullRequestOpened(Event):
    slice_id: SliceId
    pull_request_number: PullRequestNumber


@dataclass(frozen=True)
class PullRequestMerged(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class PullRequestApproved(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class PullRequestClosed(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class ReviewChangesRequested(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class ReReviewRequired(Event):
    slice_id: SliceId
    pull_request_number: PullRequestNumber


@dataclass(frozen=True)
class ReviewChangesUnaddressed(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class ReviewCompleted(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class HumanDecisionRequired(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class BlockingReviewDetected(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class AgentRunFailed(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class ImplementationInterrupted(Event):
    slice_id: SliceId
    run_id: str


@dataclass(frozen=True)
class ImplementationIncomplete(Event):
    slice_id: SliceId
    run_id: str


@dataclass(frozen=True)
class ReviewPhaseInterrupted(Event):
    slice_id: SliceId
    run_id: str


@dataclass(frozen=True)
class ReviewPhaseIncomplete(Event):
    slice_id: SliceId
    run_id: str


@dataclass(frozen=True)
class SliceReadyToDispatch(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class AgentWorkspaceAbandoned(Event):
    run_id: str


@dataclass(frozen=True)
class AgentRunAbandoned(Event):
    run_id: str

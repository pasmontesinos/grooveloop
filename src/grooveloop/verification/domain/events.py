from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.domain.event import Event

if TYPE_CHECKING:
    from grooveloop.verification.domain.pull_request_number import PullRequestNumber
    from grooveloop.verification.domain.slice_id import SliceId


@dataclass(frozen=True)
class SliceReadyToVerify(Event):
    slice_id: SliceId
    pull_request_number: PullRequestNumber
    title: str
    description: str


@dataclass(frozen=True)
class VerificationConcluded(Event):
    slice_id: SliceId


@dataclass(frozen=True)
class VerificationRunFailed(Event):
    slice_id: SliceId
    run_id: str
    pull_request_number: PullRequestNumber
    title: str
    description: str


@dataclass(frozen=True)
class VerificationIncomplete(Event):
    slice_id: SliceId
    run_id: str
    pull_request_number: PullRequestNumber
    title: str
    description: str

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Protocol

from grooveloop.bootstrap import container
from grooveloop.cli.invocation_inputs import bind_invocation_inputs
from grooveloop.delivery.domain.events import (
    ImplementationIncomplete,
    ImplementationInterrupted,
    PullRequestApproved,
    ReviewPhaseIncomplete,
    ReviewPhaseInterrupted,
    SliceReadyToDispatch,
)
from grooveloop.delivery.domain.slice_repository import SliceRepository
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.agent_run_abandoned_detector import AgentRunAbandonedDetector
from grooveloop.delivery.infrastructure.detectors.agent_run_failed_detector import (
    AgentRunFailedDetector,
)
from grooveloop.delivery.infrastructure.detectors.agent_workspace_abandoned_detector import (
    AgentWorkspaceAbandonedDetector,
)
from grooveloop.delivery.infrastructure.detectors.implementation_incomplete_detector import (
    ImplementationIncompleteDetector,
)
from grooveloop.delivery.infrastructure.detectors.implementation_interrupted_detector import (
    ImplementationInterruptedDetector,
)
from grooveloop.delivery.infrastructure.detectors.pull_request_approved_detector import (
    PullRequestApprovedDetector,
)
from grooveloop.delivery.infrastructure.detectors.pull_request_closed_detector import (
    PullRequestClosedDetector,
)
from grooveloop.delivery.infrastructure.detectors.pull_request_merged_detector import (
    PullRequestMergedDetector,
)
from grooveloop.delivery.infrastructure.detectors.pull_request_opened_detector import (
    PullRequestOpenedDetector,
)
from grooveloop.delivery.infrastructure.detectors.re_review_required_detector import (
    ReReviewRequiredDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_changes_requested_detector import (
    ReviewChangesRequestedDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_changes_unaddressed_detector import (
    ReviewChangesUnaddressedDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_outcome_detector import (
    ReviewOutcomeDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_phase_incomplete_detector import (
    ReviewPhaseIncompleteDetector,
)
from grooveloop.delivery.infrastructure.detectors.review_phase_interrupted_detector import (
    ReviewPhaseInterruptedDetector,
)
from grooveloop.delivery.infrastructure.detectors.slice_ready_to_dispatch_detector import (
    SliceReadyToDispatchDetector,
)
from grooveloop.learning.infrastructure.detectors.lesson_captured_detector import LessonCapturedDetector
from grooveloop.learning.infrastructure.detectors.lesson_resolved_detector import LessonResolvedDetector
from grooveloop.learning.infrastructure.detectors.refinement_outcome_detector import RefinementOutcomeDetector
from grooveloop.shared.application.events.event_dispatcher import EventDispatcher
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.slicing.infrastructure.detectors.story_completed_detector import StoryCompletedDetector
from grooveloop.slicing.infrastructure.detectors.story_ready_to_slice_detector import StoryReadyToSliceDetector
from grooveloop.verification.domain.events import VerificationIncomplete, VerificationRunFailed
from grooveloop.verification.infrastructure.detectors.slice_ready_to_verify_detector import SliceReadyToVerifyDetector
from grooveloop.verification.infrastructure.detectors.verification_concluded_detector import (
    VerificationConcludedDetector,
)
from grooveloop.verification.infrastructure.detectors.verification_incomplete_detector import (
    VerificationIncompleteDetector,
)
from grooveloop.verification.infrastructure.detectors.verification_run_failed_detector import (
    VerificationRunFailedDetector,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice_id import SliceId
    from grooveloop.shared.domain.event import Event


class _Detector(Protocol):
    def detect(self) -> Iterator[Event]: ...


_DispatchingEvent = (
    SliceReadyToDispatch
    | ImplementationInterrupted
    | ImplementationIncomplete
    | PullRequestApproved
    | ReviewPhaseInterrupted
    | ReviewPhaseIncomplete
    | VerificationRunFailed
    | VerificationIncomplete
)

DETECTORS: list[type[_Detector]] = [
    StoryReadyToSliceDetector,
    PullRequestOpenedDetector,
    ReviewOutcomeDetector,
    PullRequestApprovedDetector,
    AgentRunFailedDetector,
    ImplementationInterruptedDetector,
    ImplementationIncompleteDetector,
    PullRequestMergedDetector,
    PullRequestClosedDetector,
    ReviewChangesRequestedDetector,
    ReReviewRequiredDetector,
    ReviewChangesUnaddressedDetector,
    ReviewPhaseInterruptedDetector,
    ReviewPhaseIncompleteDetector,
    SliceReadyToDispatchDetector,
    SliceReadyToVerifyDetector,
    VerificationConcludedDetector,
    VerificationRunFailedDetector,
    VerificationIncompleteDetector,
    StoryCompletedDetector,
    LessonCapturedDetector,
    RefinementOutcomeDetector,
    LessonResolvedDetector,
]


def run(
    repo_full_name: str,
    workdir: str = ".",
    *,
    story: int | None = None,
    verify_deploy: bool = False,
    max_review_rounds: int = 0,
    max_parallel_slices: int = 1,
    journal_enabled: bool = False,
    max_retries: int = 0,
    auto_merge: bool = False,
) -> int:
    bind_invocation_inputs(
        repo_full_name,
        workdir,
        verify_deploy=verify_deploy,
        max_review_rounds=max_review_rounds,
        max_parallel_slices=max_parallel_slices,
        journal_enabled=journal_enabled,
        max_retries=max_retries,
        auto_merge=auto_merge,
    )

    _close_abandoned_runs(repo_full_name)

    failure: Exception | None = None

    try:
        _drive_domain(repo_full_name, story)
    except Exception as error:
        failure = error

    _sweep_workspaces(repo_full_name)

    if failure is not None:
        print(f"[fail] run tick in {repo_full_name}: {failure}", file=sys.stderr)

        return ExitCode.FAILURE

    print(f"[ok]   ran tick in {repo_full_name}")

    return ExitCode.OK


def _drive_domain(repo_full_name: str, story: int | None) -> None:
    container.get(GithubReadCache).flush()

    dispatcher = container.get(EventDispatcher)
    scope = _story_scope(story)

    for detector_type in DETECTORS:
        for event in container.get(detector_type).detect():
            if scope is not None and not _within_scope(event, scope):
                continue

            if isinstance(event, _DispatchingEvent):
                _dispatch_slice(dispatcher, event, repo_full_name)
                continue

            dispatcher.dispatch(event)


def _dispatch_slice(dispatcher: EventDispatcher, event: _DispatchingEvent, repo_full_name: str) -> None:
    try:
        dispatcher.dispatch(event)
    except Exception as error:
        print(f"[warn] dispatch failed for slice {event.slice_id.value} in {repo_full_name}: {error}", file=sys.stderr)


def _close_abandoned_runs(repo_full_name: str) -> None:
    try:
        dispatcher = container.get(EventDispatcher)
        events = list(container.get(AgentRunAbandonedDetector).detect())
    except Exception as error:
        print(f"[warn] closing abandoned runs failed in {repo_full_name}: {error}", file=sys.stderr)

        return

    for event in events:
        try:
            dispatcher.dispatch(event)
        except Exception as error:
            print(f"[warn] closing failed for run {event.run_id} in {repo_full_name}: {error}", file=sys.stderr)


def _sweep_workspaces(repo_full_name: str) -> None:
    try:
        dispatcher = container.get(EventDispatcher)
        events = list(container.get(AgentWorkspaceAbandonedDetector).detect())
    except Exception as error:
        print(f"[warn] sweep failed in {repo_full_name}: {error}", file=sys.stderr)

        return

    for event in events:
        try:
            dispatcher.dispatch(event)
        except Exception as error:
            print(f"[warn] sweep failed for run {event.run_id} in {repo_full_name}: {error}", file=sys.stderr)


def _story_scope(story: int | None) -> tuple[str, set[str]] | None:
    if story is None:
        return None

    story_value = str(story)
    slice_repository = container.get(SliceRepository)
    slice_values = {a_slice.id.value for a_slice in slice_repository.search(story_id=StoryId(story_value))}

    return story_value, slice_values


def _within_scope(event: Event, scope: tuple[str, set[str]]) -> bool:
    story_value, slice_values = scope
    event_story: StoryId | None = getattr(event, "story_id", None)
    if event_story is not None:
        return event_story.value == story_value

    event_slice: SliceId | None = getattr(event, "slice_id", None)
    if event_slice is not None:
        return event_slice.value in slice_values

    return True

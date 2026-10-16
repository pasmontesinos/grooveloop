from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.exceptions import IllegalSliceTransitionError
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.shared.domain.agent_run_cause import AgentRunCause

if TYPE_CHECKING:
    from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
    from grooveloop.delivery.domain.review_comment import ReviewComment
    from grooveloop.delivery.domain.slice_id import SliceId
    from grooveloop.delivery.domain.story_id import StoryId
    from grooveloop.shared.domain.agent_run import AgentRun

_AUTO_MERGE_VERDICTS = {ReviewVerdict.APPROVE, ReviewVerdict.MINOR}

_IMPLEMENTING = frozenset({SliceStatus.DISPATCHED})
_UNDER_REVIEW = frozenset({SliceStatus.UNDER_REVIEW})
_ADDRESSING_CHANGES = frozenset({SliceStatus.CHANGES_REQUESTED})
_REVIEW_PHASES = _UNDER_REVIEW | _ADDRESSING_CHANGES
_AWAITING_A_HUMAN = frozenset({SliceStatus.PR_OPEN, SliceStatus.BLOCKED})
_IN_PROGRESS = _IMPLEMENTING | _REVIEW_PHASES | _AWAITING_A_HUMAN

_DISPATCH_SOURCES = frozenset({SliceStatus.PENDING})
_START_REVIEW_SOURCES = _IMPLEMENTING | _ADDRESSING_CHANGES
_COMPLETE_REVIEW_SOURCES = _UNDER_REVIEW
_BLOCK_SOURCES = _UNDER_REVIEW
_REQUEST_CHANGES_SOURCES = _AWAITING_A_HUMAN | _UNDER_REVIEW
_MERGE_SOURCES = _IN_PROGRESS
_CLOSE_SOURCES = _IN_PROGRESS
_FAIL_SOURCES = _IMPLEMENTING | _REVIEW_PHASES


class Slice:
    def __init__(
        self,
        id: SliceId,
        status: SliceStatus,
        story_id: StoryId | None = None,
        title: str = "",
        description: str = "",
        pull_request: PullRequest | None = None,
        pull_request_number: PullRequestNumber | None = None,
        agent_run_id: str | None = None,
        review_verdict: ReviewVerdict = ReviewVerdict.EMPTY,
        review_rounds: int = 0,
        depends_on: list[SliceId] | None = None,
        retries: int = 0,
        failure_cause: AgentRunCause = AgentRunCause.EMPTY,
    ) -> None:
        self._id = id
        self._status = status
        self._story_id = story_id
        self._title = title
        self._description = description
        self._pull_request = pull_request
        self._pull_request_number = pull_request_number
        self._agent_run_id = agent_run_id
        self._review_verdict = review_verdict
        self._review_rounds = review_rounds
        self._depends_on = depends_on
        self._retries = retries
        self._failure_cause = failure_cause

    @property
    def id(self) -> SliceId:
        return self._id

    @property
    def story_id(self) -> StoryId | None:
        return self._story_id

    @property
    def status(self) -> SliceStatus:
        return self._status

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def pull_request(self) -> PullRequest | None:
        return self._pull_request

    @property
    def pull_request_number(self) -> PullRequestNumber | None:
        if self._pull_request is not None:
            return self._pull_request.number

        return self._pull_request_number

    @property
    def agent_run_id(self) -> str | None:
        return self._agent_run_id

    @property
    def review_verdict(self) -> ReviewVerdict:
        return self._review_verdict

    @property
    def review_rounds(self) -> int:
        return self._review_rounds

    @property
    def depends_on(self) -> list[SliceId] | None:
        return self._depends_on

    @property
    def retries(self) -> int:
        return self._retries

    @property
    def failure_cause(self) -> AgentRunCause:
        return self._failure_cause

    @staticmethod
    def tracks_pull_request_in(status: SliceStatus) -> bool:
        return status in _IN_PROGRESS

    def can_be_dispatched(self) -> bool:
        return self._status in _DISPATCH_SOURCES

    def can_start_review(self) -> bool:
        return self._status in _START_REVIEW_SOURCES

    def can_complete_review(self) -> bool:
        return self._status in _COMPLETE_REVIEW_SOURCES

    def can_be_blocked(self) -> bool:
        return self._status in _BLOCK_SOURCES

    def can_request_changes(self) -> bool:
        return self._status in _REQUEST_CHANGES_SOURCES

    def can_address_changes(self, automatic: bool, max_review_rounds: int) -> bool:
        if not self.can_request_changes():
            return False

        return not automatic or self._has_a_review_round_left(max_review_rounds)

    def can_be_merged(self) -> bool:
        return self._status in _MERGE_SOURCES

    def can_be_closed_without_merge(self) -> bool:
        return self._status in _CLOSE_SOURCES

    def is_implementing(self) -> bool:
        return self._status in _IMPLEMENTING

    def is_under_review(self) -> bool:
        return self._status in _UNDER_REVIEW

    def is_addressing_changes(self) -> bool:
        return self._status in _ADDRESSING_CHANGES

    def is_in_review_phase(self) -> bool:
        return self._status in _REVIEW_PHASES

    def is_in_progress(self) -> bool:
        return self._status in _IN_PROGRESS

    def is_merged(self) -> bool:
        return self._status is SliceStatus.MERGED

    def is_dispatchable(self, slices: list[Slice]) -> bool:
        if not self.can_be_dispatched():
            return False

        dependencies = self.dependencies(slices)
        if dependencies is None:
            return False

        return all(dependency.is_merged() for dependency in dependencies)

    def dependencies(self, slices: list[Slice]) -> list[Slice] | None:
        if self._depends_on is None:
            index = next((i for i, a_slice in enumerate(slices) if a_slice.id == self._id), len(slices))

            return slices[:index]

        by_id = {a_slice.id: a_slice for a_slice in slices}
        if any(slice_id not in by_id for slice_id in self._depends_on):
            return None

        return [by_id[slice_id] for slice_id in self._depends_on]

    def record_agent_run(self, run: AgentRun) -> None:
        self._agent_run_id = run.run_id

    def retry_agent_run(self, run: AgentRun) -> None:
        self._agent_run_id = run.run_id
        self._retries += 1

    def consume_review_round(self) -> None:
        self._review_rounds += 1

    def clear_review_rounds(self) -> None:
        self._review_rounds = 0

    def needs_a_human_decision(self) -> bool:
        return self._review_verdict is ReviewVerdict.BLOCKED

    def deserves_a_correction(self, max_review_rounds: int) -> bool:
        return self._asks_for_a_correction(max_review_rounds) and self._has_a_fresh_review_summary()

    def awaits_its_review_summary(self, max_review_rounds: int) -> bool:
        return self._asks_for_a_correction(max_review_rounds) and not self._has_a_fresh_review_summary()

    def has_a_review_outcome(self) -> bool:
        return self._review_verdict is not ReviewVerdict.EMPTY or self._has_a_fresh_review_summary()

    def awaits_requested_changes(self) -> bool:
        if self._status not in _AWAITING_A_HUMAN or self._pull_request is None:
            return False

        return self._pull_request.has_unaddressed_comments()

    def pending_directives(self) -> list[ReviewComment]:
        return self._pull_request.pending_directives() if self._pull_request is not None else []

    def addressed_directives_without_mark(self) -> list[ReviewComment]:
        return self._pull_request.addressed_directives_without_mark() if self._pull_request is not None else []

    def taken_directives(self) -> list[ReviewComment]:
        return self._pull_request.taken_directives() if self._pull_request is not None else []

    def has_commits_after_review(self) -> bool:
        return self._pull_request is not None and self._pull_request.has_commits_after_review()

    def lacks_commits_after_review(self) -> bool:
        return self._pull_request is not None and not self._pull_request.has_commits_after_review()

    def is_auto_mergeable(self) -> bool:
        if self._status is not SliceStatus.PR_OPEN:
            return False

        return self._review_verdict in _AUTO_MERGE_VERDICTS

    def lacks_review_phase_artifact(self) -> bool:
        if self._pull_request is None:
            return False

        if self.is_under_review():
            return self._review_verdict is ReviewVerdict.EMPTY and not self._has_a_fresh_review_summary()

        if self.is_addressing_changes():
            return self.lacks_commits_after_review()

        return False

    def misses_verdict_or_correction(self) -> bool:
        if self._pull_request is None:
            return False

        if self.is_under_review():
            return self._review_verdict is ReviewVerdict.EMPTY

        if self.is_addressing_changes():
            return self.lacks_commits_after_review()

        return False

    def anchor_pull_request(self, number: PullRequestNumber) -> None:
        self._pull_request = PullRequest.anchor(number)

    def dispatch(self) -> None:
        self._transition(_DISPATCH_SOURCES, SliceStatus.DISPATCHED)

    def start_review(self) -> None:
        self._transition(_START_REVIEW_SOURCES, SliceStatus.UNDER_REVIEW)
        self._review_verdict = ReviewVerdict.EMPTY

    def complete_review(self) -> None:
        self._transition(_COMPLETE_REVIEW_SOURCES, SliceStatus.PR_OPEN)

    def block(self) -> None:
        self._transition(_BLOCK_SOURCES, SliceStatus.BLOCKED)

    def request_changes(self) -> None:
        self._transition(_REQUEST_CHANGES_SOURCES, SliceStatus.CHANGES_REQUESTED)

    def mark_merged(self) -> None:
        self._transition(_MERGE_SOURCES, SliceStatus.MERGED)

    def close_without_merge(self) -> None:
        self._transition(_CLOSE_SOURCES, SliceStatus.FAILED)

    def fail(self, cause: AgentRunCause = AgentRunCause.EMPTY) -> None:
        self._transition(_FAIL_SOURCES, SliceStatus.FAILED)
        self._failure_cause = cause

    def _has_a_review_round_left(self, max_review_rounds: int) -> bool:
        return self._review_rounds < max_review_rounds

    def _asks_for_a_correction(self, max_review_rounds: int) -> bool:
        return self._review_verdict is ReviewVerdict.BLOCKING and self._has_a_review_round_left(max_review_rounds)

    def _has_a_fresh_review_summary(self) -> bool:
        return self._pull_request is not None and self._pull_request.has_a_fresh_review_summary()

    def _transition(self, allowed: frozenset[SliceStatus], target: SliceStatus) -> None:
        if self._status not in allowed:
            raise IllegalSliceTransitionError(f"Cannot move slice {self._id} from {self._status} to {target}")

        self._status = target
        if target is not SliceStatus.FAILED:
            self._retries = 0
            self._failure_cause = AgentRunCause.EMPTY

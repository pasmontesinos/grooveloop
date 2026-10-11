from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from grooveloop.delivery.domain.exceptions import IllegalSliceTransitionError
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.shared.domain.agent_run import AgentRun
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice

TRANSITIONS = [
    ("dispatch", {SliceStatus.PENDING}, SliceStatus.DISPATCHED),
    ("start_review", {SliceStatus.DISPATCHED, SliceStatus.CHANGES_REQUESTED}, SliceStatus.UNDER_REVIEW),
    ("complete_review", {SliceStatus.UNDER_REVIEW}, SliceStatus.PR_OPEN),
    ("block", {SliceStatus.UNDER_REVIEW}, SliceStatus.BLOCKED),
    (
        "request_changes",
        {SliceStatus.PR_OPEN, SliceStatus.BLOCKED, SliceStatus.UNDER_REVIEW},
        SliceStatus.CHANGES_REQUESTED,
    ),
    (
        "mark_merged",
        {
            SliceStatus.DISPATCHED,
            SliceStatus.UNDER_REVIEW,
            SliceStatus.PR_OPEN,
            SliceStatus.CHANGES_REQUESTED,
            SliceStatus.BLOCKED,
        },
        SliceStatus.MERGED,
    ),
    (
        "close_without_merge",
        {
            SliceStatus.DISPATCHED,
            SliceStatus.UNDER_REVIEW,
            SliceStatus.PR_OPEN,
            SliceStatus.CHANGES_REQUESTED,
            SliceStatus.BLOCKED,
        },
        SliceStatus.FAILED,
    ),
    (
        "fail",
        {SliceStatus.DISPATCHED, SliceStatus.UNDER_REVIEW, SliceStatus.CHANGES_REQUESTED},
        SliceStatus.FAILED,
    ),
]


TABLE = {method: (allowed, target) for method, allowed, target in TRANSITIONS}
GUARDS = [
    ("dispatch", "can_be_dispatched"),
    ("start_review", "can_start_review"),
    ("complete_review", "can_complete_review"),
    ("block", "can_be_blocked"),
    ("request_changes", "can_request_changes"),
    ("mark_merged", "can_be_merged"),
    ("close_without_merge", "can_be_closed_without_merge"),
]
IN_PROGRESS_STATUSES = {
    SliceStatus.DISPATCHED,
    SliceStatus.UNDER_REVIEW,
    SliceStatus.PR_OPEN,
    SliceStatus.CHANGES_REQUESTED,
    SliceStatus.BLOCKED,
}
PHASES = [
    ("is_implementing", {SliceStatus.DISPATCHED}),
    ("is_under_review", {SliceStatus.UNDER_REVIEW}),
    ("is_addressing_changes", {SliceStatus.CHANGES_REQUESTED}),
    ("is_in_review_phase", {SliceStatus.UNDER_REVIEW, SliceStatus.CHANGES_REQUESTED}),
    ("is_in_progress", IN_PROGRESS_STATUSES),
    ("is_merged", {SliceStatus.MERGED}),
]
TERMINAL_STATUSES = [SliceStatus.MERGED, SliceStatus.FAILED]
PHASE_CHANGES = [transition for transition in TRANSITIONS if transition[2] is not SliceStatus.FAILED]


class TestSliceLifecycle:
    @pytest.mark.parametrize(("method", "allowed", "target"), TRANSITIONS)
    def test_should_transition_from_allowed_status(
        self, method: str, allowed: set[SliceStatus], target: SliceStatus
    ) -> None:
        for status in allowed:
            a_slice = SliceMother.create(status=status)

            getattr(a_slice, method)()

            assert a_slice.status == target

    @pytest.mark.parametrize(("method", "allowed", "target"), TRANSITIONS)
    def test_should_reject_transition_from_disallowed_status(
        self, method: str, allowed: set[SliceStatus], target: SliceStatus
    ) -> None:
        for status in set(SliceStatus) - allowed:
            a_slice = SliceMother.create(status=status)

            with pytest.raises(IllegalSliceTransitionError):
                getattr(a_slice, method)()

    def test_should_start_with_no_review_rounds_consumed(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW)

        assert a_slice.review_rounds == 0

    def test_should_count_every_consumed_review_round(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW)

        a_slice.consume_review_round()
        a_slice.consume_review_round()

        assert a_slice.review_rounds == 2

    def test_should_clear_the_review_verdict_when_a_new_review_starts(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.CHANGES_REQUESTED, review_verdict=ReviewVerdict.BLOCKING)

        a_slice.start_review()

        assert a_slice.review_verdict == ReviewVerdict.EMPTY

    @pytest.mark.parametrize(("method", "allowed", "target"), PHASE_CHANGES)
    def test_should_clear_the_retries_when_the_slice_changes_phase(
        self, method: str, allowed: set[SliceStatus], target: SliceStatus
    ) -> None:
        for status in allowed:
            a_slice = SliceMother.create(status=status, retries=2)

            getattr(a_slice, method)()

            assert a_slice.retries == 0

    def test_should_keep_the_retries_when_the_slice_fails(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW, retries=2)

        a_slice.fail(AgentRunCause.NETWORK)

        assert a_slice.retries == 2

    def test_should_clear_the_failure_cause_when_a_recovered_slice_is_dispatched_again(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.PENDING, retries=2, failure_cause=AgentRunCause.NETWORK)

        a_slice.dispatch()

        assert a_slice.retries == 0
        assert a_slice.failure_cause is AgentRunCause.EMPTY

    @pytest.mark.parametrize("verdict", [ReviewVerdict.APPROVE, ReviewVerdict.MINOR])
    def test_should_be_auto_mergeable_when_the_pr_is_open_with_an_approving_verdict(
        self, verdict: ReviewVerdict
    ) -> None:
        a_slice = SliceMother.create(status=SliceStatus.PR_OPEN, review_verdict=verdict)

        assert a_slice.is_auto_mergeable()

    @pytest.mark.parametrize("verdict", [ReviewVerdict.BLOCKING, ReviewVerdict.BLOCKED, ReviewVerdict.EMPTY])
    def test_should_not_be_auto_mergeable_without_an_approving_verdict(self, verdict: ReviewVerdict) -> None:
        a_slice = SliceMother.create(status=SliceStatus.PR_OPEN, review_verdict=verdict)

        assert not a_slice.is_auto_mergeable()

    def test_should_not_be_auto_mergeable_outside_pr_open(self) -> None:
        for status in set(SliceStatus) - {SliceStatus.PR_OPEN}:
            a_slice = SliceMother.create(status=status, review_verdict=ReviewVerdict.APPROVE)

            assert not a_slice.is_auto_mergeable()


_statuses = st.sampled_from(list(SliceStatus))
_events = st.sampled_from([method for method, _, _ in TRANSITIONS])
_retries = st.integers(min_value=0, max_value=10)
_causes = st.sampled_from(list(AgentRunCause))
_verdicts = st.sampled_from(list(ReviewVerdict))


def _apply(a_slice: Slice, event: str, cause: AgentRunCause) -> None:
    if event == "fail":
        a_slice.fail(cause)
    else:
        getattr(a_slice, event)()


class TestSliceLifecycleProperties:
    @given(status=_statuses, guard=st.sampled_from(GUARDS))
    def test_should_allow_a_transition_exactly_when_the_table_allows_it(
        self, status: SliceStatus, guard: tuple[str, str]
    ) -> None:
        event, query = guard
        a_slice = SliceMother.create(status=status)

        assert getattr(a_slice, query)() is (status in TABLE[event][0])

    @given(status=_statuses, phase=st.sampled_from(PHASES))
    def test_should_tell_the_phase_of_the_slice(self, status: SliceStatus, phase: tuple[str, set[SliceStatus]]) -> None:
        query, statuses = phase
        a_slice = SliceMother.create(status=status)

        assert getattr(a_slice, query)() is (status in statuses)

    @given(status=_statuses)
    def test_should_fail_only_from_a_phase_with_an_agent_at_work(self, status: SliceStatus) -> None:
        a_slice = SliceMother.create(status=status)

        assert (a_slice.is_implementing() or a_slice.is_in_review_phase()) is (status in TABLE["fail"][0])

    @given(status=_statuses, event=_events, retries=_retries, cause=_causes, verdict=_verdicts)
    def test_should_follow_the_table_or_reject_without_changing_the_slice(
        self, status: SliceStatus, event: str, retries: int, cause: AgentRunCause, verdict: ReviewVerdict
    ) -> None:
        a_slice = SliceMother.create(status=status, retries=retries, failure_cause=cause, review_verdict=verdict)
        allowed, target = TABLE[event]

        if status in allowed:
            _apply(a_slice, event, cause)

            assert a_slice.status is target
        else:
            with pytest.raises(IllegalSliceTransitionError):
                _apply(a_slice, event, cause)

            assert a_slice.status is status
            assert a_slice.retries == retries
            assert a_slice.failure_cause is cause
            assert a_slice.review_verdict is verdict

    @given(status=_statuses, events=st.lists(st.tuples(_events, _causes), max_size=20))
    def test_should_follow_the_table_along_any_sequence_of_events(
        self, status: SliceStatus, events: list[tuple[str, AgentRunCause]]
    ) -> None:
        a_slice = SliceMother.create(status=status)
        expected = status

        for event, cause in events:
            allowed, target = TABLE[event]
            if expected in allowed:
                _apply(a_slice, event, cause)
                expected = target
            else:
                with pytest.raises(IllegalSliceTransitionError):
                    _apply(a_slice, event, cause)

            assert a_slice.status is expected

    @given(status=st.sampled_from(TERMINAL_STATUSES), events=st.lists(st.tuples(_events, _causes), min_size=1))
    def test_should_keep_a_terminal_slice_terminal(
        self, status: SliceStatus, events: list[tuple[str, AgentRunCause]]
    ) -> None:
        a_slice = SliceMother.create(status=status)

        for event, cause in events:
            with pytest.raises(IllegalSliceTransitionError):
                _apply(a_slice, event, cause)

        assert a_slice.status is status

    @given(status=_statuses, event=_events, retries=_retries, cause=_causes)
    def test_should_clear_the_retries_on_every_transition_except_the_one_to_failed(
        self, status: SliceStatus, event: str, retries: int, cause: AgentRunCause
    ) -> None:
        allowed, target = TABLE[event]
        a_slice = SliceMother.create(status=status, retries=retries, failure_cause=cause)

        if status in allowed:
            _apply(a_slice, event, cause)

            if target is SliceStatus.FAILED:
                assert a_slice.retries == retries
            else:
                assert a_slice.retries == 0
                assert a_slice.failure_cause is AgentRunCause.EMPTY

    @given(status=st.sampled_from(sorted(TABLE["fail"][0])), retries=_retries, cause=_causes)
    def test_should_record_the_cause_when_the_slice_fails(
        self, status: SliceStatus, retries: int, cause: AgentRunCause
    ) -> None:
        a_slice = SliceMother.create(status=status, retries=retries)

        a_slice.fail(cause)

        assert a_slice.failure_cause is cause
        assert a_slice.retries == retries

    @given(status=_statuses, retries=_retries, attempts=st.integers(min_value=1, max_value=5))
    def test_should_count_every_retry_without_changing_the_phase(
        self, status: SliceStatus, retries: int, attempts: int
    ) -> None:
        a_slice = SliceMother.create(status=status, retries=retries)

        for attempt in range(attempts):
            a_slice.retry_agent_run(AgentRun(run_id=f"run-{attempt}", pid=attempt))

        assert a_slice.retries == retries + attempts
        assert a_slice.status is status
        assert a_slice.agent_run_id == f"run-{attempts - 1}"

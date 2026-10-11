from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import BlockingReviewDetected, HumanDecisionRequired, ReviewCompleted
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.review_outcome_detector import (
    ReviewOutcomeDetector,
)
from grooveloop.delivery.infrastructure.max_review_rounds import MaxReviewRounds
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice


def _slice_with_review_signals(
    status: SliceStatus,
    has_review_summary: bool,
    review_verdict: ReviewVerdict = ReviewVerdict.EMPTY,
    review_rounds: int = 0,
) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=status,
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            review_summary_at=datetime(2026, 6, 2, tzinfo=UTC) if has_review_summary else None,
        ),
        agent_run_id="run-1",
        review_verdict=review_verdict,
        review_rounds=review_rounds,
    )


def _detector(
    repository: FakeSliceRepository,
    max_review_rounds: int = 0,
    outcome: AgentOutcome = AgentOutcome.SUCCEEDED,
) -> ReviewOutcomeDetector:
    return ReviewOutcomeDetector(
        slice_repository=repository,
        agent_runner=FakeAgentRunner(outcome=outcome),
        max_review_rounds=MaxReviewRounds(max_review_rounds),
    )


class TestReviewOutcomeDetector:
    def test_emits_event_for_under_review_slice_with_a_review_summary(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_review_signals(SliceStatus.UNDER_REVIEW, has_review_summary=True)]}
        )
        detector = _detector(repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_emits_event_for_under_review_slice_with_a_review_verdict_label(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=False,
                        review_verdict=ReviewVerdict.BLOCKING,
                    )
                ]
            }
        )
        detector = _detector(repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_does_not_emit_without_a_review_summary(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_review_signals(SliceStatus.UNDER_REVIEW, has_review_summary=False)]}
        )
        detector = _detector(repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_for_non_under_review_slice(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_review_signals(SliceStatus.PR_OPEN, has_review_summary=True)]}
        )
        detector = _detector(repository)

        assert list(detector.detect()) == []

    def test_asks_for_a_human_decision_when_the_verdict_is_blocked(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=True,
                        review_verdict=ReviewVerdict.BLOCKED,
                    )
                ]
            }
        )
        detector = _detector(repository)

        events = list(detector.detect())

        assert events == [HumanDecisionRequired(slice_id=SliceId("12"))]

    def test_closes_the_review_when_the_verdict_is_not_blocked(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=False,
                        review_verdict=ReviewVerdict.BLOCKING,
                    )
                ]
            }
        )
        detector = _detector(repository)

        events = list(detector.detect())

        assert events == [ReviewCompleted(slice_id=SliceId("12"))]

    def test_asks_for_a_correction_when_the_verdict_is_blocking_and_a_round_is_left(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=True,
                        review_verdict=ReviewVerdict.BLOCKING,
                    )
                ]
            }
        )

        events = list(_detector(repository, max_review_rounds=1).detect())

        assert events == [BlockingReviewDetected(slice_id=SliceId("12"))]

    def test_closes_the_review_when_the_blocking_verdict_has_no_round_left(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=True,
                        review_verdict=ReviewVerdict.BLOCKING,
                        review_rounds=1,
                    )
                ]
            }
        )

        events = list(_detector(repository, max_review_rounds=1).detect())

        assert events == [ReviewCompleted(slice_id=SliceId("12"))]

    def test_asks_for_no_correction_when_the_verdict_is_blocked(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=True,
                        review_verdict=ReviewVerdict.BLOCKED,
                    )
                ]
            }
        )

        events = list(_detector(repository, max_review_rounds=1).detect())

        assert events == [HumanDecisionRequired(slice_id=SliceId("12"))]

    def test_asks_for_no_correction_when_the_verdict_is_approve(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=True,
                        review_verdict=ReviewVerdict.APPROVE,
                    )
                ]
            }
        )

        events = list(_detector(repository, max_review_rounds=1).detect())

        assert events == [ReviewCompleted(slice_id=SliceId("12"))]

    def test_waits_for_the_summary_while_the_reviewer_is_still_running(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=False,
                        review_verdict=ReviewVerdict.BLOCKING,
                    )
                ]
            }
        )

        events = list(_detector(repository, max_review_rounds=1, outcome=AgentOutcome.RUNNING).detect())

        assert events == []

    def test_closes_the_review_when_the_reviewer_finished_without_a_summary(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_review_signals(
                        SliceStatus.UNDER_REVIEW,
                        has_review_summary=False,
                        review_verdict=ReviewVerdict.BLOCKING,
                    )
                ]
            }
        )

        events = list(_detector(repository, max_review_rounds=1, outcome=AgentOutcome.SUCCEEDED).detect())

        assert events == [ReviewCompleted(slice_id=SliceId("12"))]

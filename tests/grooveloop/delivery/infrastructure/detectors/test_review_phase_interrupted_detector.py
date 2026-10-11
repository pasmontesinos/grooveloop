from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import ReviewPhaseInterrupted
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.review_phase_interrupted_detector import (
    ReviewPhaseInterruptedDetector,
)
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.comment_directive import CommentDirective
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice


def _pull_request(last_reviewed_day: int = 3, last_commit_day: int = 2) -> PullRequest:
    return PullRequest(
        number=PullRequestNumber(42),
        comments=[
            ReviewComment(
                body="use the SliceRepository port",
                path="src/x.py",
                line=10,
                thread_id="555",
                created_at=datetime(2026, 6, last_reviewed_day, tzinfo=UTC),
                directives=frozenset({CommentDirective.IMPLEMENT}),
            )
        ],
        last_commit_at=datetime(2026, 6, last_commit_day, tzinfo=UTC),
    )


def _slice_with_a_pull_request_and_an_agent_run(
    status: SliceStatus,
    pull_request: PullRequest | None = None,
    review_verdict: ReviewVerdict = ReviewVerdict.EMPTY,
) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=status,
        pull_request=pull_request or _pull_request(),
        agent_run_id="run-1",
        review_verdict=review_verdict,
    )


def _detector(a_slice: Slice, outcome: AgentOutcome = AgentOutcome.INTERRUPTED) -> ReviewPhaseInterruptedDetector:
    return ReviewPhaseInterruptedDetector(
        slice_repository=FakeSliceRepository({StoryId("10"): [a_slice]}),
        agent_runner=FakeAgentRunner(outcome=outcome),
    )


class TestReviewPhaseInterruptedDetector:
    def test_emits_the_run_of_a_reviewer_interrupted_without_a_verdict(self) -> None:
        detector = _detector(_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW))

        assert list(detector.detect()) == [ReviewPhaseInterrupted(slice_id=SliceId("12"), run_id="run-1")]

    def test_emits_the_run_of_a_correction_interrupted_without_pushing(self) -> None:
        detector = _detector(_slice_with_a_pull_request_and_an_agent_run(SliceStatus.CHANGES_REQUESTED))

        assert list(detector.detect()) == [ReviewPhaseInterrupted(slice_id=SliceId("12"), run_id="run-1")]

    def test_ignores_a_reviewer_that_failed(self) -> None:
        detector = _detector(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW), outcome=AgentOutcome.FAILED
        )

        assert list(detector.detect()) == []

    def test_ignores_an_interrupted_reviewer_that_already_declared_its_verdict(self) -> None:
        detector = _detector(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW, review_verdict=ReviewVerdict.APPROVE)
        )

        assert list(detector.detect()) == []

    def test_ignores_an_interrupted_correction_that_pushed_commits_after_the_review(self) -> None:
        a_slice = _slice_with_a_pull_request_and_an_agent_run(
            SliceStatus.CHANGES_REQUESTED, _pull_request(last_reviewed_day=2, last_commit_day=3)
        )

        assert list(_detector(a_slice).detect()) == []

    def test_ignores_an_interrupted_implementation(self) -> None:
        detector = _detector(SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, agent_run_id="run-1"))

        assert list(detector.detect()) == []

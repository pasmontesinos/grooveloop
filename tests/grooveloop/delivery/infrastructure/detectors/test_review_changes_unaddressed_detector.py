from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.review_changes_unaddressed_detector import (
    ReviewChangesUnaddressedDetector,
)
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.comment_directive import CommentDirective
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice


def _comment(day: int) -> ReviewComment:
    return ReviewComment(
        body="use the SliceRepository port",
        path="src/x.py",
        line=10,
        thread_id="555",
        created_at=datetime(2026, 6, day, tzinfo=UTC),
        directives=frozenset({CommentDirective.IMPLEMENT}),
    )


def _slice_with_a_reviewed_pull_request(
    status: SliceStatus,
    last_reviewed_day: int,
    last_commit_day: int,
    agent_run_id: str | None = "run-1",
) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=status,
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(last_reviewed_day)],
            last_commit_at=datetime(2026, 6, last_commit_day, tzinfo=UTC),
        ),
        agent_run_id=agent_run_id,
    )


class TestReviewChangesUnaddressedDetector:
    def test_leaves_the_interrupted_correction_to_its_recovery(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_a_reviewed_pull_request(
                        SliceStatus.CHANGES_REQUESTED, last_reviewed_day=3, last_commit_day=2
                    )
                ]
            }
        )
        detector = ReviewChangesUnaddressedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.INTERRUPTED)
        )

        events = list(detector.detect())

        assert events == []

    def test_emits_event_when_the_agent_failed_without_pushing(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_a_reviewed_pull_request(
                        SliceStatus.CHANGES_REQUESTED, last_reviewed_day=3, last_commit_day=2
                    )
                ]
            }
        )
        detector = ReviewChangesUnaddressedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_does_not_emit_while_the_agent_is_still_running(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_a_reviewed_pull_request(
                        SliceStatus.CHANGES_REQUESTED, last_reviewed_day=3, last_commit_day=2
                    )
                ]
            }
        )
        detector = ReviewChangesUnaddressedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.RUNNING)
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_when_the_agent_pushed_commits_after_the_review(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_a_reviewed_pull_request(
                        SliceStatus.CHANGES_REQUESTED, last_reviewed_day=2, last_commit_day=3
                    )
                ]
            }
        )
        detector = ReviewChangesUnaddressedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_for_a_non_changes_requested_slice(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_a_reviewed_pull_request(SliceStatus.PR_OPEN, last_reviewed_day=3, last_commit_day=2)
                ]
            }
        )
        detector = ReviewChangesUnaddressedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_when_the_slice_has_no_recorded_run(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_a_reviewed_pull_request(
                        SliceStatus.CHANGES_REQUESTED, last_reviewed_day=3, last_commit_day=2, agent_run_id=None
                    )
                ]
            }
        )
        detector = ReviewChangesUnaddressedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        assert list(detector.detect()) == []

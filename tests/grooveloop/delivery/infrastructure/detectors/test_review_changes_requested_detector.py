from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.review_changes_requested_detector import (
    ReviewChangesRequestedDetector,
)
from grooveloop.shared.domain.comment_directive import CommentDirective
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
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


def _slice_with_a_pull_request(
    status: SliceStatus,
    comment_day: int | None = None,
    last_commit_day: int | None = None,
    review_summary_day: int | None = None,
) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=status,
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(comment_day)] if comment_day else [],
            last_commit_at=datetime(2026, 6, last_commit_day, tzinfo=UTC) if last_commit_day else None,
            review_summary_at=datetime(2026, 6, review_summary_day, tzinfo=UTC) if review_summary_day else None,
        ),
    )


class TestReviewChangesRequestedDetector:
    def test_emits_event_for_pr_open_slice_with_an_inline_comment(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request(SliceStatus.PR_OPEN, comment_day=2)]}
        )
        detector = ReviewChangesRequestedDetector(slice_repository=repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_does_not_emit_when_there_are_no_inline_comments(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_slice_with_a_pull_request(SliceStatus.PR_OPEN)]})
        detector = ReviewChangesRequestedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_for_non_pr_open_slice(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request(SliceStatus.CHANGES_REQUESTED, comment_day=2)]}
        )
        detector = ReviewChangesRequestedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_when_there_are_commits_after_the_comment(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request(SliceStatus.PR_OPEN, comment_day=2, last_commit_day=3)]}
        )
        detector = ReviewChangesRequestedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_does_not_emit_when_an_approving_review_summary_follows_the_commit_after_the_comment(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_a_pull_request(
                        SliceStatus.PR_OPEN, comment_day=2, last_commit_day=3, review_summary_day=4
                    )
                ]
            }
        )
        detector = ReviewChangesRequestedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

    def test_emits_event_for_a_blocked_slice_with_an_unaddressed_comment(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request(SliceStatus.BLOCKED, comment_day=2)]}
        )
        detector = ReviewChangesRequestedDetector(slice_repository=repository)

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_does_not_emit_for_a_blocked_slice_without_comments(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): [_slice_with_a_pull_request(SliceStatus.BLOCKED)]})
        detector = ReviewChangesRequestedDetector(slice_repository=repository)

        assert list(detector.detect()) == []

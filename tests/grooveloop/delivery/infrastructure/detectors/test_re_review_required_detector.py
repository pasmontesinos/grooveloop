from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import ReReviewRequired
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.re_review_required_detector import ReReviewRequiredDetector
from grooveloop.shared.domain.comment_directive import CommentDirective
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice


def _corrected_slice(review_rounds: int = 0, has_commits: bool = True) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=SliceStatus.CHANGES_REQUESTED,
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            review_summary_at=datetime(2026, 6, 2, tzinfo=UTC),
            last_commit_at=datetime(2026, 6, 3 if has_commits else 1, tzinfo=UTC),
        ),
        review_rounds=review_rounds,
    )


def _human_corrected_slice(status: SliceStatus = SliceStatus.CHANGES_REQUESTED) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=status,
        pull_request=PullRequest(
            number=PullRequestNumber(42),
            comments=[
                ReviewComment(
                    body="/grooveloop-implement: rename the method",
                    created_at=datetime(2026, 6, 2, tzinfo=UTC),
                    directives=frozenset({CommentDirective.IMPLEMENT}),
                )
            ],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        ),
    )


def _detector(a_slice: Slice) -> ReReviewRequiredDetector:
    return ReReviewRequiredDetector(slice_repository=FakeSliceRepository({StoryId("10"): [a_slice]}))


class TestReReviewRequiredDetector:
    def test_asks_for_a_new_review_when_a_round_is_still_left(self) -> None:
        events = list(_detector(_corrected_slice(review_rounds=1)).detect())

        assert events == [ReReviewRequired(slice_id=SliceId("12"), pull_request_number=PullRequestNumber(42))]

    def test_asks_for_a_new_review_when_the_last_round_is_spent(self) -> None:
        events = list(_detector(_corrected_slice(review_rounds=2)).detect())

        assert events == [ReReviewRequired(slice_id=SliceId("12"), pull_request_number=PullRequestNumber(42))]

    def test_asks_for_a_new_review_of_a_human_correction(self) -> None:
        events = list(_detector(_human_corrected_slice()).detect())

        assert events == [ReReviewRequired(slice_id=SliceId("12"), pull_request_number=PullRequestNumber(42))]

    def test_emits_nothing_without_commits_after_the_review(self) -> None:
        assert list(_detector(_corrected_slice(has_commits=False)).detect()) == []

    def test_does_not_emit_for_a_non_changes_requested_slice(self) -> None:
        events = list(_detector(_human_corrected_slice(status=SliceStatus.PR_OPEN)).detect())

        assert events == []

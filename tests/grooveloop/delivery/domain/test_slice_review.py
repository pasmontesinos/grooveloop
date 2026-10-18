from __future__ import annotations

from datetime import UTC, datetime

import pytest

from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.shared.domain.comment_directive import CommentDirective
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother

_REVIEWED_AT = datetime(2026, 6, 2, tzinfo=UTC)
_BEFORE_THE_REVIEW = datetime(2026, 6, 1, tzinfo=UTC)
_AFTER_THE_REVIEW = datetime(2026, 6, 3, tzinfo=UTC)


def _summarized_pull_request(last_commit_at: datetime | None = _BEFORE_THE_REVIEW) -> PullRequest:
    return PullRequest(
        number=PullRequestNumber(42), comments=[], last_commit_at=last_commit_at, review_summary_at=_REVIEWED_AT
    )


def _pull_request_with_an_implement_comment() -> PullRequest:
    comment = ReviewComment(
        body="/grooveloop-implement",
        created_at=_REVIEWED_AT,
        directives=frozenset({CommentDirective.IMPLEMENT}),
    )

    return PullRequest(number=PullRequestNumber(42), comments=[comment], last_commit_at=_BEFORE_THE_REVIEW)


def _pull_request_with_a_no_changes_reply_after_a_taken_directive() -> PullRequest:
    directive = ReviewComment(
        body="/grooveloop-implement",
        created_at=_BEFORE_THE_REVIEW,
        directives=frozenset({CommentDirective.IMPLEMENT}),
        marks=frozenset({DirectiveMark.TAKEN}),
        taken_at=_REVIEWED_AT,
    )

    return PullRequest(
        number=PullRequestNumber(42),
        comments=[directive],
        last_commit_at=_BEFORE_THE_REVIEW,
        review_summary_at=_BEFORE_THE_REVIEW,
        no_changes_reply_at=_AFTER_THE_REVIEW,
    )


class TestSliceReviewCompletion:
    def test_should_need_a_human_decision_when_the_reviewer_blocks_it(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW, review_verdict=ReviewVerdict.BLOCKED)

        assert a_slice.needs_a_human_decision() is True

    @pytest.mark.parametrize("verdict", [ReviewVerdict.EMPTY, ReviewVerdict.APPROVE, ReviewVerdict.BLOCKING])
    def test_should_not_need_a_human_decision_with_another_verdict(self, verdict: ReviewVerdict) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW, review_verdict=verdict)

        assert a_slice.needs_a_human_decision() is False

    def test_should_deserve_a_correction_when_a_blocking_review_is_summarized_and_rounds_remain(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW,
            review_verdict=ReviewVerdict.BLOCKING,
            review_rounds=1,
            pull_request=_summarized_pull_request(),
        )

        assert a_slice.deserves_a_correction(max_review_rounds=2) is True

    def test_should_not_deserve_a_correction_when_no_rounds_remain(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW,
            review_verdict=ReviewVerdict.BLOCKING,
            review_rounds=2,
            pull_request=_summarized_pull_request(),
        )

        assert a_slice.deserves_a_correction(max_review_rounds=2) is False

    def test_should_not_deserve_a_correction_before_the_summary_is_published(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW,
            review_verdict=ReviewVerdict.BLOCKING,
            pull_request=PullRequest(number=PullRequestNumber(42), comments=[]),
        )

        assert a_slice.deserves_a_correction(max_review_rounds=2) is False

    def test_should_not_deserve_a_correction_without_a_blocking_verdict(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW,
            review_verdict=ReviewVerdict.MINOR,
            pull_request=_summarized_pull_request(),
        )

        assert a_slice.deserves_a_correction(max_review_rounds=2) is False

    def test_should_await_its_summary_when_a_blocking_verdict_has_a_round_left_and_no_summary(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW,
            review_verdict=ReviewVerdict.BLOCKING,
            pull_request=PullRequest(number=PullRequestNumber(42), comments=[]),
        )

        assert a_slice.awaits_its_review_summary(max_review_rounds=1) is True

    def test_should_not_await_its_summary_when_no_rounds_remain(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW,
            review_verdict=ReviewVerdict.BLOCKING,
            pull_request=PullRequest(number=PullRequestNumber(42), comments=[]),
        )

        assert a_slice.awaits_its_review_summary(max_review_rounds=0) is False

    def test_should_not_await_its_summary_once_it_is_published(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW,
            review_verdict=ReviewVerdict.BLOCKING,
            pull_request=_summarized_pull_request(),
        )

        assert a_slice.awaits_its_review_summary(max_review_rounds=1) is False

    def test_should_have_a_review_outcome_once_the_reviewer_marks_a_verdict(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW, review_verdict=ReviewVerdict.APPROVE)

        assert a_slice.has_a_review_outcome() is True

    def test_should_have_a_review_outcome_once_the_reviewer_publishes_a_fresh_summary(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW, pull_request=_summarized_pull_request())

        assert a_slice.has_a_review_outcome() is True

    def test_should_have_no_review_outcome_with_a_summary_older_than_the_last_commit(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW, pull_request=_summarized_pull_request(last_commit_at=_AFTER_THE_REVIEW)
        )

        assert a_slice.has_a_review_outcome() is False


class TestSliceAddressingChanges:
    def test_should_let_the_human_ask_for_changes_without_rounds_left(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.PR_OPEN, review_rounds=3)

        assert a_slice.can_address_changes(automatic=False, max_review_rounds=0) is True

    def test_should_let_the_loop_ask_for_changes_while_rounds_remain(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW, review_rounds=1)

        assert a_slice.can_address_changes(automatic=True, max_review_rounds=2) is True

    def test_should_not_let_the_loop_ask_for_changes_without_rounds_left(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW, review_rounds=2)

        assert a_slice.can_address_changes(automatic=True, max_review_rounds=2) is False

    def test_should_not_address_changes_when_the_table_does_not_allow_the_request(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.CHANGES_REQUESTED)

        assert a_slice.can_address_changes(automatic=False, max_review_rounds=3) is False

    @pytest.mark.parametrize("status", [SliceStatus.PR_OPEN, SliceStatus.BLOCKED])
    def test_should_await_the_changes_the_human_asked_for(self, status: SliceStatus) -> None:
        a_slice = SliceMother.create(status=status, pull_request=_pull_request_with_an_implement_comment())

        assert a_slice.awaits_requested_changes() is True

    def test_should_not_await_the_changes_the_human_asked_for_while_under_review(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW, pull_request=_pull_request_with_an_implement_comment()
        )

        assert a_slice.awaits_requested_changes() is False

    def test_should_not_await_changes_without_a_pull_request(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.PR_OPEN)

        assert a_slice.awaits_requested_changes() is False


class TestSliceCorrectionAfterReview:
    def test_should_have_a_correction_after_the_review_when_the_pull_request_has_commits_after_it(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.CHANGES_REQUESTED,
            pull_request=_summarized_pull_request(last_commit_at=_AFTER_THE_REVIEW),
        )

        assert a_slice.has_correction_after_review() is True
        assert a_slice.lacks_correction_after_review() is False

    def test_should_lack_a_correction_after_the_review_when_the_pull_request_has_no_commits_after_it(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.CHANGES_REQUESTED, pull_request=_summarized_pull_request())

        assert a_slice.has_correction_after_review() is False
        assert a_slice.lacks_correction_after_review() is True

    def test_should_have_a_correction_after_the_review_with_a_no_changes_reply_to_a_taken_directive(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.CHANGES_REQUESTED,
            pull_request=_pull_request_with_a_no_changes_reply_after_a_taken_directive(),
        )

        assert a_slice.has_correction_after_review() is True
        assert a_slice.lacks_correction_after_review() is False
        assert a_slice.declines_the_changes() is True

    def test_should_neither_have_nor_lack_a_correction_after_the_review_without_a_pull_request(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.CHANGES_REQUESTED)

        assert a_slice.has_correction_after_review() is False
        assert a_slice.lacks_correction_after_review() is False
        assert a_slice.declines_the_changes() is False


class TestSliceReviewPhaseWithoutItsResult:
    def test_should_miss_the_verdict_of_a_review_even_with_its_summary(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.UNDER_REVIEW, pull_request=_summarized_pull_request())

        assert a_slice.misses_verdict_or_correction() is True

    def test_should_not_miss_the_verdict_once_the_reviewer_marks_it(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.UNDER_REVIEW,
            review_verdict=ReviewVerdict.BLOCKING,
            pull_request=_summarized_pull_request(),
        )

        assert a_slice.misses_verdict_or_correction() is False

    def test_should_miss_the_correction_without_commits_after_the_review(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.CHANGES_REQUESTED, pull_request=_summarized_pull_request())

        assert a_slice.misses_verdict_or_correction() is True

    def test_should_not_miss_the_correction_with_commits_after_the_review(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.CHANGES_REQUESTED,
            pull_request=_summarized_pull_request(last_commit_at=_AFTER_THE_REVIEW),
        )

        assert a_slice.misses_verdict_or_correction() is False

    def test_should_not_miss_the_correction_with_a_no_changes_reply_to_a_taken_directive(self) -> None:
        a_slice = SliceMother.create(
            status=SliceStatus.CHANGES_REQUESTED,
            pull_request=_pull_request_with_a_no_changes_reply_after_a_taken_directive(),
        )

        assert a_slice.misses_verdict_or_correction() is False
        assert a_slice.lacks_review_phase_artifact() is False

    @pytest.mark.parametrize("status", [SliceStatus.UNDER_REVIEW, SliceStatus.CHANGES_REQUESTED])
    def test_should_not_miss_anything_without_a_pull_request(self, status: SliceStatus) -> None:
        a_slice = SliceMother.create(status=status)

        assert a_slice.misses_verdict_or_correction() is False

    def test_should_not_miss_anything_outside_the_review_phases(self) -> None:
        a_slice = SliceMother.create(status=SliceStatus.PR_OPEN, pull_request=_summarized_pull_request())

        assert a_slice.misses_verdict_or_correction() is False

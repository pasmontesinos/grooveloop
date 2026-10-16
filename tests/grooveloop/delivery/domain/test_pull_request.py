from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.shared.domain.comment_directive import CommentDirective


def _comment(
    day: int,
    directives: frozenset[CommentDirective] = frozenset({CommentDirective.IMPLEMENT}),
    marks: frozenset[DirectiveMark] = frozenset(),
    taken_on: int | None = None,
) -> ReviewComment:
    return ReviewComment(
        body="use the SliceRepository port",
        path="src/x.py",
        line=10,
        thread_id="555",
        created_at=datetime(2026, 6, day, tzinfo=UTC),
        directives=directives,
        id=f"comment-{day}",
        marks=marks,
        taken_at=datetime(2026, 6, taken_on, tzinfo=UTC) if taken_on is not None else None,
    )


_TAKEN = frozenset({DirectiveMark.TAKEN})
_ADDRESSED = frozenset({DirectiveMark.TAKEN, DirectiveMark.ADDRESSED})


class TestPullRequest:
    def test_has_unaddressed_comments_when_an_implement_comment_is_newer_than_the_last_commit(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(3)],
            last_commit_at=datetime(2026, 6, 2, tzinfo=UTC),
        )

        assert pull_request.has_unaddressed_comments() is True

    def test_has_no_unaddressed_comments_when_the_last_commit_is_newer(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2)],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.has_unaddressed_comments() is False

    def test_has_no_unaddressed_comments_without_any_comment(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])

        assert pull_request.has_unaddressed_comments() is False

    def test_has_unaddressed_comments_when_there_are_implement_comments_without_commits(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[_comment(2)])

        assert pull_request.has_unaddressed_comments() is True

    def test_has_no_unaddressed_comments_when_the_directive_is_not_implement(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2, directives=frozenset({CommentDirective.LEARN}))],
        )

        assert pull_request.has_unaddressed_comments() is False

    def test_has_commits_after_review_when_last_commit_is_newer_than_the_latest_implement_comment(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2)],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is True

    def test_has_no_commits_after_review_when_last_commit_is_not_newer(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(3)],
            last_commit_at=datetime(2026, 6, 2, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is False

    def test_has_no_commits_after_review_without_comments_or_commit_date(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])

        assert pull_request.has_commits_after_review() is False

    def test_the_review_baseline_ignores_the_agent_reply_without_an_implement_directive(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2), _comment(5, directives=frozenset())],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is True
        assert pull_request.has_unaddressed_comments() is False

    def test_has_no_unaddressed_comments_when_an_approving_review_summary_follows_the_commit_after_the_directive(
        self,
    ) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2)],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 4, tzinfo=UTC),
        )

        assert pull_request.has_unaddressed_comments() is False

    def test_has_unaddressed_comments_when_the_directive_is_newer_than_the_last_commit_whatever_the_summary(
        self,
    ) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(3)],
            last_commit_at=datetime(2026, 6, 2, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 1, tzinfo=UTC),
        )

        assert pull_request.has_unaddressed_comments() is True

    def test_is_closed_without_merge_when_closed_and_not_merged(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[], closed=True)

        assert pull_request.is_closed_without_merge() is True

    def test_is_not_closed_without_merge_when_merged(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[], closed=True, merged=True)

        assert pull_request.is_closed_without_merge() is False

    def test_is_not_closed_without_merge_when_still_open(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])

        assert pull_request.is_closed_without_merge() is False

    def test_is_open_when_neither_merged_nor_closed(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])

        assert pull_request.is_open() is True

    def test_is_not_open_when_merged(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[], closed=True, merged=True)

        assert pull_request.is_open() is False

    def test_is_not_open_when_closed_without_merge(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[], closed=True)

        assert pull_request.is_open() is False

    def test_reports_a_fresh_review_summary_when_hydrated_with_one(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42), comments=[], review_summary_at=datetime(2026, 6, 2, tzinfo=UTC)
        )

        assert pull_request.has_a_fresh_review_summary() is True

    def test_reports_no_fresh_review_summary_by_default(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])

        assert pull_request.has_a_fresh_review_summary() is False

    def test_reports_no_fresh_review_summary_when_the_last_commit_is_newer(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 2, tzinfo=UTC),
        )

        assert pull_request.has_a_fresh_review_summary() is False

    def test_has_commits_after_review_when_the_last_commit_is_newer_than_the_review_summary(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 2, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is True

    def test_has_no_commits_after_review_when_the_review_summary_is_newer(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            last_commit_at=datetime(2026, 6, 2, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is False

    def test_the_review_baseline_takes_the_latest_of_the_summary_and_the_implement_comments(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(4)],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 2, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is False


class TestPullRequestDirectiveMarks:
    def test_a_directive_with_the_addressed_mark_is_not_pending_even_if_newer_than_the_last_commit(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(3, marks=_ADDRESSED)],
            last_commit_at=datetime(2026, 6, 2, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 1, tzinfo=UTC),
        )

        assert pull_request.pending_directives() == []
        assert pull_request.has_unaddressed_comments() is False

    def test_a_taken_directive_without_the_addressed_mark_is_pending_even_with_a_later_commit(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2, marks=_TAKEN)],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.pending_directives() == [_comment(2, marks=_TAKEN)]
        assert pull_request.has_unaddressed_comments() is True

    def test_an_unmarked_directive_on_a_marked_pull_request_is_pending_even_if_older_than_the_last_commit(
        self,
    ) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2, marks=_ADDRESSED), _comment(3)],
            last_commit_at=datetime(2026, 6, 4, tzinfo=UTC),
        )

        assert pull_request.pending_directives() == [_comment(3)]

    def test_without_marks_the_pending_directives_are_the_ones_not_older_than_the_last_commit(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2), _comment(4), _comment(5, directives=frozenset())],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.pending_directives() == [_comment(4)]

    def test_without_marks_the_directives_older_than_the_last_commit_are_addressed_without_a_mark(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2), _comment(4)],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.addressed_directives_without_mark() == [_comment(2)]

    def test_with_marks_no_directive_is_addressed_without_a_mark(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2, marks=_ADDRESSED), _comment(3)],
            last_commit_at=datetime(2026, 6, 4, tzinfo=UTC),
        )

        assert pull_request.addressed_directives_without_mark() == []

    def test_the_taken_directives_are_the_ones_with_the_taken_mark_and_without_the_addressed_one(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2, marks=_ADDRESSED), _comment(3, marks=_TAKEN), _comment(4)],
        )

        assert pull_request.taken_directives() == [_comment(3, marks=_TAKEN)]

    def test_the_review_baseline_of_a_marked_pull_request_ignores_the_directives_without_a_mark(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2, marks=_TAKEN), _comment(4)],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is True

    def test_the_review_baseline_of_a_marked_pull_request_takes_the_latest_marked_directive(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2, marks=_ADDRESSED), _comment(4, marks=_TAKEN)],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is False

    def test_a_directive_taken_after_the_last_commit_holds_the_re_review_although_it_is_older_than_the_summary(
        self,
    ) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(1, marks=_TAKEN, taken_on=7)],
            last_commit_at=datetime(2026, 6, 6, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is False

    def test_a_commit_after_the_take_of_a_directive_requires_the_re_review(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(1, marks=_TAKEN, taken_on=7)],
            last_commit_at=datetime(2026, 6, 8, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is True

    def test_a_human_commit_before_the_take_of_a_pending_directive_does_not_require_the_re_review(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(2, marks=_ADDRESSED, taken_on=3), _comment(4, marks=_TAKEN, taken_on=7)],
            last_commit_at=datetime(2026, 6, 6, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
        )

        assert pull_request.has_commits_after_review() is False


class TestPullRequestCorrectionWithoutChanges:
    def test_a_no_changes_reply_after_the_take_of_a_directive_is_a_correction_without_commits(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(1, marks=_TAKEN, taken_on=7)],
            last_commit_at=datetime(2026, 6, 6, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 8, tzinfo=UTC),
        )

        assert pull_request.has_a_correction_after_review() is True

    def test_a_no_changes_reply_before_the_take_of_a_directive_is_not_a_correction(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(1, marks=_TAKEN, taken_on=7)],
            last_commit_at=datetime(2026, 6, 6, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 6, tzinfo=UTC),
        )

        assert pull_request.has_a_correction_after_review() is False

    def test_a_no_changes_reply_after_the_summary_of_a_blocking_verdict_is_a_correction_without_commits(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 6, tzinfo=UTC),
        )

        assert pull_request.has_a_correction_after_review() is True
        assert pull_request.declines_the_changes() is True

    def test_a_no_changes_reply_before_the_summary_of_a_blocking_verdict_is_not_a_correction(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 4, tzinfo=UTC),
        )

        assert pull_request.has_a_correction_after_review() is False

    def test_still_declines_the_changes_once_its_directives_are_addressed(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(3, marks=_ADDRESSED)],
            last_commit_at=datetime(2026, 6, 1, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 2, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 4, tzinfo=UTC),
        )

        assert pull_request.declines_the_changes() is True

    def test_a_commit_after_the_review_is_a_correction(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(1, marks=_TAKEN, taken_on=7)],
            last_commit_at=datetime(2026, 6, 8, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
        )

        assert pull_request.has_a_correction_after_review() is True

    def test_declines_the_changes_with_a_no_changes_reply_and_no_commits_after_the_review(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(1, marks=_TAKEN, taken_on=7)],
            last_commit_at=datetime(2026, 6, 6, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 8, tzinfo=UTC),
        )

        assert pull_request.declines_the_changes() is True

    def test_does_not_decline_the_changes_when_it_also_has_commits_after_the_review(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[_comment(1, marks=_TAKEN, taken_on=7)],
            last_commit_at=datetime(2026, 6, 9, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 8, tzinfo=UTC),
        )

        assert pull_request.declines_the_changes() is False

    def test_reports_no_fresh_review_summary_when_the_no_changes_reply_is_newer(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 5, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 6, tzinfo=UTC),
        )

        assert pull_request.has_a_fresh_review_summary() is False

    def test_reports_a_fresh_review_summary_newer_than_the_no_changes_reply(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            last_commit_at=datetime(2026, 6, 3, tzinfo=UTC),
            review_summary_at=datetime(2026, 6, 7, tzinfo=UTC),
            no_changes_reply_at=datetime(2026, 6, 6, tzinfo=UTC),
        )

        assert pull_request.has_a_fresh_review_summary() is True

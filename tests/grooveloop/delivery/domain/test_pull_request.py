from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.shared.domain.comment_directive import CommentDirective


def _comment(
    day: int, directives: frozenset[CommentDirective] = frozenset({CommentDirective.IMPLEMENT})
) -> ReviewComment:
    return ReviewComment(
        body="use the SliceRepository port",
        path="src/x.py",
        line=10,
        thread_id="555",
        created_at=datetime(2026, 6, day, tzinfo=UTC),
        directives=directives,
    )


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

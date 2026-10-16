from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
    from grooveloop.delivery.domain.review_comment import ReviewComment


class PullRequest:
    def __init__(
        self,
        number: PullRequestNumber,
        comments: list[ReviewComment],
        last_commit_at: datetime | None = None,
        merged: bool = False,
        closed: bool = False,
        review_summary_at: datetime | None = None,
        no_changes_reply_at: datetime | None = None,
    ) -> None:
        self._number = number
        self._comments = comments
        self._last_commit_at = last_commit_at
        self._merged = merged
        self._closed = closed
        self._review_summary_at = review_summary_at
        self._no_changes_reply_at = no_changes_reply_at

    @classmethod
    def anchor(cls, number: PullRequestNumber) -> Self:
        return cls(number=number, comments=[])

    @property
    def number(self) -> PullRequestNumber:
        return self._number

    @property
    def comments(self) -> list[ReviewComment]:
        return self._comments

    @property
    def last_commit_at(self) -> datetime | None:
        return self._last_commit_at

    def is_merged(self) -> bool:
        return self._merged

    def is_open(self) -> bool:
        return not self._merged and not self._closed

    def is_closed_without_merge(self) -> bool:
        return self._closed and not self._merged

    def has_a_fresh_review_summary(self) -> bool:
        if self._review_summary_at is None:
            return False

        last_change_at = max(
            (instant for instant in (self._last_commit_at, self._no_changes_reply_at) if instant is not None),
            default=None,
        )
        if last_change_at is None:
            return True

        return self._review_summary_at > last_change_at

    def has_unaddressed_comments(self) -> bool:
        return len(self.pending_directives()) > 0

    def pending_directives(self) -> list[ReviewComment]:
        directives = self._comments_requesting_implementation()
        if self._is_marked():
            return [directive for directive in directives if not directive.is_addressed()]

        return [directive for directive in directives if self._is_newer_than_the_last_commit(directive)]

    def addressed_directives_without_mark(self) -> list[ReviewComment]:
        pending = self.pending_directives()

        return [
            directive
            for directive in self._comments_requesting_implementation()
            if directive not in pending and not directive.is_addressed()
        ]

    def taken_directives(self) -> list[ReviewComment]:
        return [directive for directive in self._comments_requesting_implementation() if directive.is_taken()]

    def has_commits_after_review(self) -> bool:
        last_reviewed_at = self._last_reviewed_at()
        if last_reviewed_at is None or self._last_commit_at is None:
            return False

        return self._last_commit_at > last_reviewed_at

    def has_a_correction_after_review(self) -> bool:
        return self.has_commits_after_review() or self._has_a_no_changes_reply_after_review()

    def declines_the_changes(self) -> bool:
        return self._has_a_no_changes_reply_after_review() and not self.has_commits_after_review()

    def _has_a_no_changes_reply_after_review(self) -> bool:
        last_reviewed_at = self._last_reviewed_at()
        if last_reviewed_at is None or self._no_changes_reply_at is None:
            return False

        return self._no_changes_reply_at > last_reviewed_at

    def _last_reviewed_at(self) -> datetime | None:
        instants = [directive.reviewed_at() for directive in self._reviewed_directives()]
        if self._review_summary_at is not None:
            instants.append(self._review_summary_at)

        return max(instants, default=None)

    def _reviewed_directives(self) -> list[ReviewComment]:
        directives = self._comments_requesting_implementation()
        if self._is_marked():
            return [directive for directive in directives if directive.is_marked()]

        return directives

    def _is_newer_than_the_last_commit(self, directive: ReviewComment) -> bool:
        return self._last_commit_at is None or directive.created_at >= self._last_commit_at

    def _is_marked(self) -> bool:
        return any(directive.is_marked() for directive in self._comments_requesting_implementation())

    def _comments_requesting_implementation(self) -> list[ReviewComment]:
        return [comment for comment in self._comments if comment.requests_implementation()]

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
    ) -> None:
        self._number = number
        self._comments = comments
        self._last_commit_at = last_commit_at
        self._merged = merged
        self._closed = closed
        self._review_summary_at = review_summary_at

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

        if self._last_commit_at is None:
            return True

        return self._review_summary_at > self._last_commit_at

    def has_unaddressed_comments(self) -> bool:
        last_directive_at = self._last_directive_at()
        if last_directive_at is None:
            return False

        return self._last_commit_at is None or self._last_commit_at <= last_directive_at

    def has_commits_after_review(self) -> bool:
        last_reviewed_at = self._last_reviewed_at()
        if last_reviewed_at is None or self._last_commit_at is None:
            return False

        return self._last_commit_at > last_reviewed_at

    def _last_reviewed_at(self) -> datetime | None:
        instants = [comment.created_at for comment in self._comments_requesting_implementation()]
        if self._review_summary_at is not None:
            instants.append(self._review_summary_at)

        return max(instants, default=None)

    def _last_directive_at(self) -> datetime | None:
        return max((comment.created_at for comment in self._comments_requesting_implementation()), default=None)

    def _comments_requesting_implementation(self) -> list[ReviewComment]:
        return [comment for comment in self._comments if comment.requests_implementation()]

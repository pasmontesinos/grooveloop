from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from github.Commit import Commit
    from github.Issue import Issue
    from github.IssueComment import IssueComment
    from github.PullRequest import PullRequest
    from github.PullRequestReview import PullRequestReview
    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache

_ISSUES_KEY_PREFIX = "issues:"
_TTL_SECONDS = 300


class CachedGithubRepo:
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._repo = repo
        self._cache = cache
        self._ttl = _TTL_SECONDS

    def issues(self, state: str, labels: list[str] | None = None) -> list[Issue]:
        key = f"{_ISSUES_KEY_PREFIX}{state}" if labels is None else f"{_ISSUES_KEY_PREFIX}{state}:{','.join(labels)}"

        return self._cache.get_or_load(key, lambda: self._fetch_issues(state, labels), self._ttl)

    def _fetch_issues(self, state: str, labels: list[str] | None) -> list[Issue]:
        if labels is None:
            return list(self._repo.get_issues(state=state))

        return list(self._repo.get_issues(state=state, labels=labels))

    def issue(self, number: int) -> Issue:
        return self._cache.get_or_load(f"issue:{number}", lambda: self._repo.get_issue(number), self._ttl)

    def pull(self, number: int) -> PullRequest:
        return self._cache.get_or_load(f"pull:{number}", lambda: self._repo.get_pull(number), self._ttl)

    def reviews_of(self, number: int) -> list[PullRequestReview]:
        return self._cache.get_or_load(f"reviews:{number}", lambda: list(self.pull(number).get_reviews()), self._ttl)

    def commits_of(self, number: int) -> list[Commit]:
        return self._cache.get_or_load(f"commits:{number}", lambda: list(self.pull(number).get_commits()), self._ttl)

    def issue_comments_of(self, number: int) -> list[IssueComment]:
        return self._cache.get_or_load(
            self._issue_comments_key(number), lambda: list(self.pull(number).get_issue_comments()), self._ttl
        )

    def create_issue(self, title: str, body: str, labels: list[str]) -> Issue:
        issue = self._repo.create_issue(title=title, body=body, labels=labels)
        self._cache.invalidate_prefix(_ISSUES_KEY_PREFIX)

        return issue

    def set_issue_labels(self, number: int, labels: list[str]) -> None:
        self.issue(number).set_labels(*labels)
        self._invalidate_issue(number)

    def add_issue_labels(self, number: int, labels: list[str]) -> None:
        self.issue(number).add_to_labels(*labels)
        self._invalidate_issue(number)

    def close_issue(self, number: int) -> None:
        self.issue(number).edit(state="closed")
        self._invalidate_issue(number)

    def comment_on(self, number: int, body: str) -> None:
        self.pull(number).create_issue_comment(body)
        self._cache.invalidate(self._issue_comments_key(number))

    def flush(self) -> None:
        self._cache.flush()

    def _invalidate_issue(self, number: int) -> None:
        self._cache.invalidate(f"issue:{number}")
        self._cache.invalidate_prefix(_ISSUES_KEY_PREFIX)

    def _issue_comments_key(self, number: int) -> str:
        return f"issue_comments:{number}"

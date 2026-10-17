from __future__ import annotations

import re
from typing import TYPE_CHECKING

from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.refinement_outcome import RefinementOutcome
from grooveloop.learning.domain.refinement_result import RefinementResult
from grooveloop.shared.infrastructure.cached_github_repo import CachedGithubRepo

if TYPE_CHECKING:
    from datetime import datetime

    from github.Issue import Issue
    from github.Repository import Repository

    from grooveloop.learning.domain.source_pull_request import SourcePullRequest
    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache

_MARKER_LABEL = "grooveloop"
_DISCARDED_MARKER = "<!-- grooveloop:learned discarded -->"
_LESSON_REFERENCE_PATTERN = re.compile(r"<!-- grooveloop:lesson pr=(\d+) -->")


class GithubRefinementResult(RefinementResult):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._repo = CachedGithubRepo(repo, cache)

    def of(self, source_pull_request: SourcePullRequest, since: datetime) -> RefinementOutcome | None:
        conventions = self._first_conventions_pull_request(source_pull_request.value, since)
        if conventions is not None:
            return RefinementOutcome(conventions_pull_request=ConventionsPullRequest(conventions), discarded=False)

        if self._is_discarded(source_pull_request.value, since):
            return RefinementOutcome(conventions_pull_request=None, discarded=True)

        return None

    def _first_conventions_pull_request(self, number: int, since: datetime) -> int | None:
        linked = [
            issue
            for issue in self._repo.issues("all", [_MARKER_LABEL])
            if issue.pull_request is not None and issue.created_at >= since and _lesson_of(issue) == number
        ]
        if not linked:
            return None

        return min(linked, key=lambda issue: issue.created_at).number

    def _is_discarded(self, number: int, since: datetime) -> bool:
        return any(
            _DISCARDED_MARKER in (comment.body or "") and comment.created_at >= since
            for comment in self._repo.issue_comments_of(number)
        )


def _lesson_of(issue: Issue) -> int | None:
    match = _LESSON_REFERENCE_PATTERN.search(issue.body or "")
    if match is None:
        return None

    return int(match.group(1))

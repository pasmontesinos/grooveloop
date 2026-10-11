from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.conventions_pull_request_status import ConventionsPullRequestStatus
from grooveloop.shared.infrastructure.cached_github_repo import CachedGithubRepo

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache


class GithubConventionsPullRequestStatus(ConventionsPullRequestStatus):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._repo = CachedGithubRepo(repo, cache)

    def is_open(self, conventions_pull_request: ConventionsPullRequest) -> bool:
        pull = self._repo.pull(conventions_pull_request.value)

        return not pull.merged and pull.state != "closed"

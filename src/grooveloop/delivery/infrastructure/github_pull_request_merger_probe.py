from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.probes.probe import Probe

if TYPE_CHECKING:
    from github.Repository import Repository


class GithubPullRequestMergerProbe(Probe):
    name = "github-pull-request-merger"

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def check(self) -> None:
        if not self._repo.allow_squash_merge:
            raise RuntimeError(f"{self._repo.full_name} does not allow squash merges")

        if not self._repo.permissions.push:
            raise RuntimeError(f"the GitHub token cannot push to {self._repo.full_name}")

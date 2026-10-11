from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.mergeability import Mergeability
from grooveloop.delivery.domain.pull_request_merger import PullRequestMerger

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.delivery.domain.pull_request_number import PullRequestNumber

_MERGE_METHOD = "squash"


class GithubPullRequestMerger(PullRequestMerger):
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def mergeability(self, number: PullRequestNumber) -> Mergeability:
        return Mergeability(self._repo.get_pull(number.value).mergeable_state)

    def merge(self, number: PullRequestNumber) -> None:
        self._repo.get_pull(number.value).merge(merge_method=_MERGE_METHOD)

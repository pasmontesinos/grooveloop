from __future__ import annotations

from typing import TYPE_CHECKING

from github import GithubException

from grooveloop.delivery.domain.mergeability import Mergeability
from grooveloop.delivery.domain.pull_request_merger import PullRequestMerger

if TYPE_CHECKING:
    from grooveloop.delivery.domain.pull_request_number import PullRequestNumber


class FakePullRequestMerger(PullRequestMerger):
    def __init__(self, mergeability: Mergeability = Mergeability.CLEAN) -> None:
        self._mergeability = mergeability
        self.consulted: list[PullRequestNumber] = []
        self.merged: list[PullRequestNumber] = []

    def mergeability(self, number: PullRequestNumber) -> Mergeability:
        self.consulted.append(number)

        return self._mergeability

    def merge(self, number: PullRequestNumber) -> None:
        self.merged.append(number)


class FailingPullRequestMerger(FakePullRequestMerger):
    def merge(self, number: PullRequestNumber) -> None:
        raise GithubException(405, {"message": "Pull Request is not mergeable"}, None)

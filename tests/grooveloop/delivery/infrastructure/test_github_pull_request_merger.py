from __future__ import annotations

from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Permissions import Permissions
from github.PullRequest import PullRequest
from github.Repository import Repository

from grooveloop.delivery.domain.mergeability import Mergeability
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.infrastructure.github_pull_request_merger import GithubPullRequestMerger
from grooveloop.delivery.infrastructure.github_pull_request_merger_probe import GithubPullRequestMergerProbe


def _permissions(push: bool) -> Any:
    permissions = create_autospec(Permissions, spec_set=True, instance=True)
    permissions.push = push

    return permissions


@pytest.fixture
def pull() -> Any:
    return create_autospec(PullRequest, spec_set=True, instance=True)


@pytest.fixture
def repo(pull: Mock) -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_pull.return_value = pull

    return repo


@pytest.mark.integration
class TestGithubPullRequestMerger:
    @pytest.mark.parametrize("mergeable_state", ["clean", "blocked", "behind", "dirty", "unstable", "unknown"])
    def test_translates_the_mergeable_state_of_the_pull_request(
        self, repo: Mock, pull: Mock, mergeable_state: str
    ) -> None:
        pull.mergeable_state = mergeable_state

        mergeability = GithubPullRequestMerger(repo).mergeability(PullRequestNumber(42))

        repo.get_pull.assert_called_once_with(42)
        assert mergeability is Mergeability(mergeable_state)

    def test_squash_merges_the_pull_request(self, repo: Mock, pull: Mock) -> None:
        GithubPullRequestMerger(repo).merge(PullRequestNumber(42))

        repo.get_pull.assert_called_once_with(42)
        pull.merge.assert_called_once_with(merge_method="squash")


@pytest.mark.integration
class TestGithubPullRequestMergerProbe:
    def test_passes_when_the_loop_may_squash_merge_in_the_repository(self, repo: Mock) -> None:
        repo.allow_squash_merge = True
        repo.permissions = _permissions(push=True)

        GithubPullRequestMergerProbe(repo).check()

    def test_fails_when_the_repository_does_not_allow_squash_merges(self, repo: Mock) -> None:
        repo.allow_squash_merge = False
        repo.permissions = _permissions(push=True)

        with pytest.raises(RuntimeError, match="squash"):
            GithubPullRequestMergerProbe(repo).check()

    def test_fails_when_the_token_cannot_push_to_the_repository(self, repo: Mock) -> None:
        repo.allow_squash_merge = True
        repo.permissions = _permissions(push=False)

        with pytest.raises(RuntimeError, match="push"):
            GithubPullRequestMergerProbe(repo).check()

    def test_should_expose_a_name(self, repo: Mock) -> None:
        assert GithubPullRequestMergerProbe(repo).name == "github-pull-request-merger"

from __future__ import annotations

from github import Github

from grooveloop.bootstrap import container
from grooveloop.delivery.domain.slice_repository import SliceRepository
from grooveloop.delivery.infrastructure.github_slice_repository import GithubSliceRepository
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from tests.playground.shared.infrastructure.github_client import github_client_for_any_repo


class TestDeliveryModule:
    def test_should_build_the_slice_repository_for_the_target_repo(self) -> None:
        github = github_client_for_any_repo()
        with container.override(TargetRepo, TargetRepo("owner/repo")), container.override(Github, github):
            slice_repository = container.get(SliceRepository)

        assert isinstance(slice_repository, GithubSliceRepository)
        github.get_repo.assert_called_once_with("owner/repo")

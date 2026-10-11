from __future__ import annotations

from github import Github

from grooveloop.bootstrap import container
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.slicing.domain.story_repository import StoryRepository
from grooveloop.slicing.infrastructure.github_story_repository import GithubStoryRepository
from tests.playground.shared.infrastructure.github_client import github_client_for_any_repo


class TestSlicingModule:
    def test_should_build_the_story_repository_for_the_target_repo(self) -> None:
        github = github_client_for_any_repo()
        with container.override(TargetRepo, TargetRepo("owner/repo")), container.override(Github, github):
            story_repository = container.get(StoryRepository)

        assert isinstance(story_repository, GithubStoryRepository)
        github.get_repo.assert_called_once_with("owner/repo")

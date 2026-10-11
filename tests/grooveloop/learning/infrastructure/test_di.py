from __future__ import annotations

from github import Github

from grooveloop.bootstrap import container
from grooveloop.learning.domain.conventions_pull_request_status import ConventionsPullRequestStatus
from grooveloop.learning.domain.learn_signal import LearnSignal
from grooveloop.learning.domain.lesson_repository import LessonRepository
from grooveloop.learning.domain.refinement_result import RefinementResult
from grooveloop.learning.infrastructure.github_conventions_pull_request_status import (
    GithubConventionsPullRequestStatus,
)
from grooveloop.learning.infrastructure.github_learn_signal import GithubLearnSignal
from grooveloop.learning.infrastructure.github_lesson_repository import GithubLessonRepository
from grooveloop.learning.infrastructure.github_refinement_result import GithubRefinementResult
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from tests.playground.shared.infrastructure.github_client import github_client_for_any_repo


class TestLearningModule:
    def test_should_build_its_github_adapters_for_the_target_repo(self) -> None:
        github = github_client_for_any_repo()
        with container.override(TargetRepo, TargetRepo("owner/repo")), container.override(Github, github):
            lesson_repository = container.get(LessonRepository)
            conventions_pull_request_status = container.get(ConventionsPullRequestStatus)
            learn_signal = container.get(LearnSignal)
            refinement_result = container.get(RefinementResult)

        assert isinstance(lesson_repository, GithubLessonRepository)
        assert isinstance(conventions_pull_request_status, GithubConventionsPullRequestStatus)
        assert isinstance(learn_signal, GithubLearnSignal)
        assert isinstance(refinement_result, GithubRefinementResult)
        github.get_repo.assert_called_once_with("owner/repo")

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import create_autospec

import pytest
from github.PullRequest import PullRequest
from github.Repository import Repository

from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.infrastructure.github_conventions_pull_request_status import (
    GithubConventionsPullRequestStatus,
)
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)

    return GithubReadCache(clock)


def _pull(number: int, merged: bool, state: str) -> Any:
    pull = create_autospec(PullRequest, spec_set=True, instance=True)
    pull.number = number
    pull.merged = merged
    pull.state = state

    return pull


def _repo(pull: Any) -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_pull.side_effect = lambda number: pull

    return repo


@pytest.mark.integration
class TestGithubConventionsPullRequestStatus:
    def test_reports_an_open_conventions_pull_request_as_open(self) -> None:
        repo = _repo(_pull(101, merged=False, state="open"))
        status = GithubConventionsPullRequestStatus(repo, _cache())

        assert status.is_open(ConventionsPullRequest(101)) is True

    def test_reports_a_merged_conventions_pull_request_as_not_open(self) -> None:
        repo = _repo(_pull(101, merged=True, state="closed"))
        status = GithubConventionsPullRequestStatus(repo, _cache())

        assert status.is_open(ConventionsPullRequest(101)) is False

    def test_reports_a_closed_conventions_pull_request_as_not_open(self) -> None:
        repo = _repo(_pull(101, merged=False, state="closed"))
        status = GithubConventionsPullRequestStatus(repo, _cache())

        assert status.is_open(ConventionsPullRequest(101)) is False

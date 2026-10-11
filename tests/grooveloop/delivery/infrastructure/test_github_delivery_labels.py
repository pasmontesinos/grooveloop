from __future__ import annotations

from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github import UnknownObjectException
from github.Label import Label
from github.Repository import Repository

from grooveloop.delivery.infrastructure.github_delivery_labels import GithubDeliveryLabels


def _missing(*names: str) -> Any:
    absent = set(names)

    def get_label(name: str) -> Any:
        if name in absent:
            raise UnknownObjectException(404, None, None)

        return create_autospec(Label, spec_set=True, instance=True)

    return get_label


@pytest.fixture
def repo() -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.full_name = "owner/repo"

    return repo


@pytest.mark.integration
class TestGithubDeliveryLabels:
    def test_creates_the_blocked_status_label_when_it_is_missing(self, repo: Mock) -> None:
        repo.get_label.side_effect = _missing("blocked")

        GithubDeliveryLabels(repo).ensure()

        created = [call.args[0] for call in repo.create_label.call_args_list]
        assert created == ["blocked"]

    def test_creates_every_missing_verdict_label(self, repo: Mock) -> None:
        repo.get_label.side_effect = _missing("review:approve", "review:minor", "review:blocking", "review:blocked")

        GithubDeliveryLabels(repo).ensure()

        created = [call.args[0] for call in repo.create_label.call_args_list]
        assert created == ["review:approve", "review:minor", "review:blocking", "review:blocked"]

    def test_does_not_recreate_a_label_that_already_exists(self, repo: Mock) -> None:
        repo.get_label.side_effect = _missing()

        GithubDeliveryLabels(repo).ensure()

        repo.create_label.assert_not_called()

    def test_asks_for_each_label_by_name_instead_of_listing_the_catalogue(self, repo: Mock) -> None:
        repo.get_label.side_effect = _missing()

        GithubDeliveryLabels(repo).ensure()

        assert repo.get_label.call_count == 12
        repo.get_labels.assert_not_called()

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github import UnknownObjectException
from github.Label import Label
from github.Repository import Repository

from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.github_slice_labels import GithubSliceLabels


@pytest.fixture
def repo() -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.full_name = "owner/repo"

    return repo


@pytest.mark.integration
class TestGithubSliceLabels:
    def test_creates_the_label_of_the_slice_when_it_is_missing(self, repo: Mock) -> None:
        repo.get_label.side_effect = UnknownObjectException(404, None, None)

        GithubSliceLabels(repo).ensure(SliceId("532"))

        repo.get_label.assert_called_once_with("slice:532")
        assert [call.args[0] for call in repo.create_label.call_args_list] == ["slice:532"]

    def test_does_not_recreate_the_label_of_the_slice_when_it_already_exists(self, repo: Mock) -> None:
        repo.get_label.return_value = create_autospec(Label, spec_set=True, instance=True)

        GithubSliceLabels(repo).ensure(SliceId("532"))

        repo.create_label.assert_not_called()

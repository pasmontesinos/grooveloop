from __future__ import annotations

from typing import Any
from unittest.mock import create_autospec

import pytest
from github import Github
from github.Requester import Requester

from grooveloop.shared.infrastructure.github_graphql import GithubGraphQLError
from grooveloop.shared.infrastructure.github_graphql_probe import GithubGraphQLProbe


def _github(data: dict[str, Any]) -> Any:
    github = create_autospec(Github, spec_set=True, instance=True)
    github.requester = create_autospec(Requester, spec_set=True, instance=True)
    github.requester.graphql_query.return_value = ({}, data)

    return github


@pytest.mark.integration
class TestGithubGraphQLProbe:
    def test_check_should_pass_when_graphql_responds(self) -> None:
        github = _github({"data": {"rateLimit": {"remaining": 4999}}})
        probe = GithubGraphQLProbe(github)

        probe.check()

        github.requester.graphql_query.assert_called_once_with("query { rateLimit { remaining } }", {})

    def test_check_should_raise_when_graphql_returns_errors(self) -> None:
        probe = GithubGraphQLProbe(_github({"data": None, "errors": [{"message": "bad credentials"}]}))

        with pytest.raises(GithubGraphQLError):
            probe.check()

    def test_should_expose_a_name(self) -> None:
        assert GithubGraphQLProbe(_github({"data": {}})).name == "github-graphql"

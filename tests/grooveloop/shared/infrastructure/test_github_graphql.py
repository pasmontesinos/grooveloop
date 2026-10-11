from __future__ import annotations

from typing import Any
from unittest.mock import create_autospec

import pytest
from github.Requester import Requester

from grooveloop.shared.infrastructure.github_graphql import GithubGraphQL, GithubGraphQLError


def _requester(data: dict[str, Any]) -> Any:
    requester = create_autospec(Requester, spec_set=True, instance=True)
    requester.graphql_query.return_value = ({}, data)

    return requester


@pytest.mark.integration
class TestGithubGraphQL:
    def test_query_returns_the_data_payload(self) -> None:
        requester = _requester({"data": {"rateLimit": {"remaining": 4999}}})
        graphql = GithubGraphQL(requester)

        result = graphql.query("query { rateLimit { remaining } }", {})

        assert result == {"rateLimit": {"remaining": 4999}}

    def test_query_forwards_document_and_variables(self) -> None:
        requester = _requester({"data": {}})
        graphql = GithubGraphQL(requester)

        graphql.query("QUERY", {"q": "repo:o/r"})

        requester.graphql_query.assert_called_once_with("QUERY", {"q": "repo:o/r"})

    def test_query_raises_loudly_on_graphql_errors(self) -> None:
        requester = _requester({"data": None, "errors": [{"message": "boom"}]})
        graphql = GithubGraphQL(requester)

        with pytest.raises(GithubGraphQLError):
            graphql.query("QUERY", {})

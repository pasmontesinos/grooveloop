from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from github.Requester import Requester


class GithubGraphQLError(Exception): ...


class GithubGraphQL:
    def __init__(self, requester: Requester) -> None:
        self._requester = requester

    def query(self, document: str, variables: dict[str, Any]) -> dict[str, Any]:
        _headers, data = self._requester.graphql_query(document, variables)
        errors = data.get("errors")

        if errors:
            raise GithubGraphQLError(str(errors))

        payload: dict[str, Any] = data["data"]

        return payload

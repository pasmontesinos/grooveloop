from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.probes.probe import Probe
from grooveloop.shared.infrastructure.github_graphql import GithubGraphQL

if TYPE_CHECKING:
    from github import Github

_RATE_LIMIT_QUERY = "query { rateLimit { remaining } }"


class GithubGraphQLProbe(Probe):
    name = "github-graphql"

    def __init__(self, github: Github) -> None:
        self._graphql = GithubGraphQL(github.requester)

    def check(self) -> None:
        self._graphql.query(_RATE_LIMIT_QUERY, {})

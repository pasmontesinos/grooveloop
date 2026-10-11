from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.application.queries.agent_session_dto_mapper import agent_session_dto_from_domain
from grooveloop.shared.application.queries.list_repo_sessions import ListRepoSessionsQuery, ListRepoSessionsQueryResult
from grooveloop.shared.application.queries.query_handler import QueryHandler

if TYPE_CHECKING:
    from grooveloop.delivery.domain.agent_session_repository import AgentSessionRepository


class ListRepoSessionsQueryHandler(QueryHandler[ListRepoSessionsQuery, ListRepoSessionsQueryResult]):
    def __init__(self, agent_session_repository: AgentSessionRepository) -> None:
        self._agent_session_repository = agent_session_repository

    def __call__(self, query: ListRepoSessionsQuery) -> ListRepoSessionsQueryResult:
        sessions = self._agent_session_repository.search(repo=query.repo)

        return ListRepoSessionsQueryResult(sessions=[agent_session_dto_from_domain(session) for session in sessions])

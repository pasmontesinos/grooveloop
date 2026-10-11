from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.application.queries.agent_session_dto_mapper import agent_session_dto_from_domain
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.shared.application.queries.query_result import QueryResult

if TYPE_CHECKING:
    from grooveloop.delivery.domain.agent_session_repository import AgentSessionRepository
    from grooveloop.shared.application.queries.list_repo_sessions import AgentSessionDTO


@dataclass(frozen=True)
class ListSliceSessionsQueryResult(QueryResult):
    sessions: list[AgentSessionDTO]


@dataclass(frozen=True)
class ListSliceSessionsQuery(Query[ListSliceSessionsQueryResult]):
    repo: str
    slice_id: str


class ListSliceSessionsQueryHandler(QueryHandler[ListSliceSessionsQuery, ListSliceSessionsQueryResult]):
    def __init__(self, agent_session_repository: AgentSessionRepository) -> None:
        self._agent_session_repository = agent_session_repository

    def __call__(self, query: ListSliceSessionsQuery) -> ListSliceSessionsQueryResult:
        slice_id = SliceId(query.slice_id)
        transcripts = self._agent_session_repository.search_transcripts(repo=query.repo, slice_id=slice_id)

        dtos = [
            agent_session_dto_from_domain(transcript.session, turn_growth=transcript.turn_growth)
            for transcript in transcripts
        ]

        return ListSliceSessionsQueryResult(sessions=dtos)

from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.agent_session_repository import AgentSessionRepository
from grooveloop.delivery.domain.agent_session_transcript import AgentSessionTranscript

if TYPE_CHECKING:
    from grooveloop.delivery.domain.agent_session import AgentSession
    from grooveloop.delivery.domain.slice_id import SliceId
    from grooveloop.shared.domain.turn_growth import TurnGrowth


class FakeAgentSessionRepository(AgentSessionRepository):
    def __init__(
        self,
        sessions: dict[tuple[str, str], list[AgentSession]],
        turn_growth: dict[tuple[str, str], list[list[TurnGrowth]]] | None = None,
    ) -> None:
        self._sessions = sessions
        self._turn_growth = turn_growth or {}

    def search(self, repo: str, slice_id: SliceId | None = None) -> list[AgentSession]:
        if slice_id is not None:
            return self._sessions.get((repo, slice_id.value), [])

        return [
            session
            for (stored_repo, _), sessions in self._sessions.items()
            if stored_repo == repo
            for session in sessions
        ]

    def search_transcripts(self, repo: str, slice_id: SliceId | None = None) -> list[AgentSessionTranscript]:
        sessions = self.search(repo, slice_id)
        if slice_id is None:
            return [AgentSessionTranscript(session=session) for session in sessions]

        growth = self._turn_growth.get((repo, slice_id.value), [])

        return [
            AgentSessionTranscript(session=session, turn_growth=growth[index] if index < len(growth) else [])
            for index, session in enumerate(sessions)
        ]

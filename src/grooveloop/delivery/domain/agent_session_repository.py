from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.domain.agent_session import AgentSession
    from grooveloop.delivery.domain.agent_session_transcript import AgentSessionTranscript
    from grooveloop.delivery.domain.slice_id import SliceId


class AgentSessionRepository(ABC):
    @abstractmethod
    def search(self, repo: str, slice_id: SliceId | None = None) -> list[AgentSession]: ...

    @abstractmethod
    def search_transcripts(self, repo: str, slice_id: SliceId | None = None) -> list[AgentSessionTranscript]: ...

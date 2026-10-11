from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.journal.domain.agent_run_context import AgentRunContext
    from grooveloop.journal.domain.agent_run_id import AgentRunId


class AgentRunContextRepository(ABC):
    @abstractmethod
    def find(self, id: AgentRunId) -> AgentRunContext | None: ...

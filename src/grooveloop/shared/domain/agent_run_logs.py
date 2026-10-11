from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_log_chunk import AgentLogChunk


class AgentRunLogs(ABC):
    @abstractmethod
    def read(self, run_id: str, offset: int) -> AgentLogChunk | None: ...

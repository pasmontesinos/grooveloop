from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_runner import AgentRunner


class AgentRunnerRegistry(ABC):
    @abstractmethod
    def runner_for(self, engine: str) -> AgentRunner: ...

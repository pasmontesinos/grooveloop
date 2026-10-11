from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_log_action import AgentLogAction
    from grooveloop.shared.domain.agent_run_reading import AgentRunReading
    from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
    from grooveloop.shared.domain.turn_growth import TurnGrowth


class AgentLogReader(ABC):
    @property
    @abstractmethod
    def engine(self) -> str: ...

    @abstractmethod
    def read(self, log_text: str) -> AgentRunReading: ...

    @abstractmethod
    def last_action(self, log_tail: str) -> str | None: ...

    @abstractmethod
    def turn_growth(self, log_text: str) -> list[TurnGrowth]: ...

    @abstractmethod
    def actions(self, log_text: str) -> list[AgentLogAction]: ...

    @abstractmethod
    def verdict(self, log_tail: str, exit_code: int) -> AgentRunVerdict: ...

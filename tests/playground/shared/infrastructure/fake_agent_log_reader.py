from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_log_reader import AgentLogReader
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_log_action import AgentLogAction
    from grooveloop.shared.domain.agent_run_reading import AgentRunReading
    from grooveloop.shared.domain.turn_growth import TurnGrowth


class FakeAgentLogReader(AgentLogReader):
    def __init__(self, engine: str, reading: AgentRunReading, action: str | None = None) -> None:
        self._engine = engine
        self._reading = reading
        self._action = action
        self.calls = 0
        self.log_text = ""
        self.action_log_tail = ""
        self.turn_growth_reading: list[TurnGrowth] = []
        self.turn_growth_calls = 0

    @property
    def engine(self) -> str:
        return self._engine

    def read(self, log_text: str) -> AgentRunReading:
        self.calls += 1
        self.log_text = log_text

        return self._reading

    def last_action(self, log_tail: str) -> str | None:
        self.action_log_tail = log_tail

        return self._action

    def turn_growth(self, log_text: str) -> list[TurnGrowth]:
        self.turn_growth_calls += 1

        return self.turn_growth_reading

    def actions(self, log_text: str) -> list[AgentLogAction]:
        return []

    def verdict(self, log_tail: str, exit_code: int) -> AgentRunVerdict:
        return AgentRunVerdict(AgentOutcome.FAILED, AgentRunCause.UNKNOWN)

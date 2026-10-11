from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_run_cause import AgentRunCause

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_runner import AgentRunner


class AgentRunFailureCause:
    def __init__(self, agent_runner: AgentRunner) -> None:
        self._agent_runner = agent_runner

    def of(self, run_id: str | None) -> AgentRunCause:
        if run_id is None:
            return AgentRunCause.EMPTY

        return self._agent_runner.verdict_of(run_id).cause

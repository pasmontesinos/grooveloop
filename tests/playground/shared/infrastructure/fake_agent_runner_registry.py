from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_runner import AgentRunner


class FakeAgentRunnerRegistry(AgentRunnerRegistry):
    def __init__(self, runner: AgentRunner) -> None:
        self.requested_engines: list[str] = []
        self._runner = runner

    def runner_for(self, engine: str) -> AgentRunner:
        self.requested_engines.append(engine)

        return self._runner

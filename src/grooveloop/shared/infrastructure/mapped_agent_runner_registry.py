from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.domain.exceptions import UnsupportedEngineError

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_runner import AgentRunner


class MappedAgentRunnerRegistry(AgentRunnerRegistry):
    def __init__(self, runners: dict[str, AgentRunner]) -> None:
        self._runners = runners

    def runner_for(self, engine: str) -> AgentRunner:
        runner = self._runners.get(engine)
        if runner is None:
            raise UnsupportedEngineError(f"unsupported engine: {engine}")

        return runner

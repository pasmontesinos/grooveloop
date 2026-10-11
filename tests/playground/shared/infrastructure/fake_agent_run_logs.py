from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_log_chunk import AgentLogChunk
from grooveloop.shared.domain.agent_run_logs import AgentRunLogs

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_log_action import AgentLogAction


class FakeAgentRunLogs(AgentRunLogs):
    def __init__(self, actions: dict[str, list[AgentLogAction]] | None = None) -> None:
        self.reads: list[tuple[str, int]] = []
        self._actions = actions or {}

    def append(self, run_id: str, action: AgentLogAction) -> None:
        self._actions.setdefault(run_id, []).append(action)

    def read(self, run_id: str, offset: int) -> AgentLogChunk | None:
        self.reads.append((run_id, offset))
        actions = self._actions.get(run_id)
        if actions is None:
            return None

        return AgentLogChunk(actions=actions[offset:], offset=len(actions))

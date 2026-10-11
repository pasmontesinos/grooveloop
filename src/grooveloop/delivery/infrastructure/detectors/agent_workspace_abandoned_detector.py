from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import AgentWorkspaceAbandoned

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.shared.domain.agent_workspaces import AgentWorkspaces

_MAX_PER_TICK = 20


class AgentWorkspaceAbandonedDetector:
    def __init__(self, agent_workspaces: AgentWorkspaces) -> None:
        self._agent_workspaces = agent_workspaces

    def detect(self) -> Iterator[AgentWorkspaceAbandoned]:
        for run_id in self._agent_workspaces.finished_run_ids()[:_MAX_PER_TICK]:
            yield AgentWorkspaceAbandoned(run_id=run_id)

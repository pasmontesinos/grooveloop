from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.remove_agent_workspace import (
    RemoveAgentWorkspaceCommand,
    RemoveAgentWorkspaceCommandHandler,
)
from grooveloop.delivery.domain.events import AgentWorkspaceAbandoned
from grooveloop.shared.application.events.event_handler import EventHandler


class RemoveAgentWorkspaceWhenAgentWorkspaceAbandoned(EventHandler[AgentWorkspaceAbandoned]):
    event_class = AgentWorkspaceAbandoned

    def handle(self, event: AgentWorkspaceAbandoned) -> None:
        handler = container.get(RemoveAgentWorkspaceCommandHandler)

        handler(RemoveAgentWorkspaceCommand(run_id=event.run_id))

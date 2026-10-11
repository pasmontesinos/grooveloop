from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.close_agent_run import CloseAgentRunCommand, CloseAgentRunCommandHandler
from grooveloop.delivery.domain.events import AgentRunAbandoned
from grooveloop.shared.application.events.event_handler import EventHandler


class CloseAgentRunWhenAgentRunAbandoned(EventHandler[AgentRunAbandoned]):
    event_class = AgentRunAbandoned

    def handle(self, event: AgentRunAbandoned) -> None:
        handler = container.get(CloseAgentRunCommandHandler)

        handler(CloseAgentRunCommand(run_id=event.run_id))

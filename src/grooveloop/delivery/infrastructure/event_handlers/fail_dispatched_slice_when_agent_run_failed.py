from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.fail_dispatched_slice import (
    FailDispatchedSliceCommand,
    FailDispatchedSliceCommandHandler,
)
from grooveloop.delivery.domain.events import AgentRunFailed
from grooveloop.shared.application.events.event_handler import EventHandler


class FailDispatchedSliceWhenAgentRunFailed(EventHandler[AgentRunFailed]):
    event_class = AgentRunFailed

    def handle(self, event: AgentRunFailed) -> None:
        handler = container.get(FailDispatchedSliceCommandHandler)

        handler(FailDispatchedSliceCommand(slice_id=event.slice_id.value))

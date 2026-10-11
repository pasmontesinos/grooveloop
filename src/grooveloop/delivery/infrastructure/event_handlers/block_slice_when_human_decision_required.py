from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.block_slice import (
    BlockSliceCommand,
    BlockSliceCommandHandler,
)
from grooveloop.delivery.domain.events import HumanDecisionRequired
from grooveloop.shared.application.events.event_handler import EventHandler


class BlockSliceWhenHumanDecisionRequired(EventHandler[HumanDecisionRequired]):
    event_class = HumanDecisionRequired

    def handle(self, event: HumanDecisionRequired) -> None:
        handler = container.get(BlockSliceCommandHandler)

        handler(BlockSliceCommand(slice_id=event.slice_id.value))

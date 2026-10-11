from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.fail_addressing_changes import (
    FailAddressingChangesCommand,
    FailAddressingChangesCommandHandler,
)
from grooveloop.delivery.domain.events import ReviewChangesUnaddressed
from grooveloop.shared.application.events.event_handler import EventHandler


class FailAddressingChangesWhenReviewChangesUnaddressed(EventHandler[ReviewChangesUnaddressed]):
    event_class = ReviewChangesUnaddressed

    def handle(self, event: ReviewChangesUnaddressed) -> None:
        handler = container.get(FailAddressingChangesCommandHandler)

        handler(FailAddressingChangesCommand(slice_id=event.slice_id.value))

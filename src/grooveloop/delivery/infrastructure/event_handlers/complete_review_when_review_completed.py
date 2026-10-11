from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.complete_review import (
    CompleteReviewCommand,
    CompleteReviewCommandHandler,
)
from grooveloop.delivery.domain.events import ReviewCompleted
from grooveloop.shared.application.events.event_handler import EventHandler


class CompleteReviewWhenReviewCompleted(EventHandler[ReviewCompleted]):
    event_class = ReviewCompleted

    def handle(self, event: ReviewCompleted) -> None:
        handler = container.get(CompleteReviewCommandHandler)

        handler(CompleteReviewCommand(slice_id=event.slice_id.value))

from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.mark_merged import (
    MarkMergedCommand,
    MarkMergedCommandHandler,
)
from grooveloop.delivery.domain.events import PullRequestMerged
from grooveloop.shared.application.events.event_handler import EventHandler


class MarkMergedWhenPullRequestMerged(EventHandler[PullRequestMerged]):
    event_class = PullRequestMerged

    def handle(self, event: PullRequestMerged) -> None:
        handler = container.get(MarkMergedCommandHandler)

        handler(MarkMergedCommand(slice_id=event.slice_id.value))

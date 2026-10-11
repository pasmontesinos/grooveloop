from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.close_without_merge import (
    CloseWithoutMergeCommand,
    CloseWithoutMergeCommandHandler,
)
from grooveloop.delivery.domain.events import PullRequestClosed
from grooveloop.shared.application.events.event_handler import EventHandler


class CloseWithoutMergeWhenPullRequestClosed(EventHandler[PullRequestClosed]):
    event_class = PullRequestClosed

    def handle(self, event: PullRequestClosed) -> None:
        handler = container.get(CloseWithoutMergeCommandHandler)

        handler(CloseWithoutMergeCommand(slice_id=event.slice_id.value))

from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.merge_pull_request import (
    MergePullRequestCommand,
    MergePullRequestCommandHandler,
)
from grooveloop.delivery.domain.events import PullRequestApproved
from grooveloop.shared.application.events.event_handler import EventHandler


class MergePullRequestWhenPullRequestApproved(EventHandler[PullRequestApproved]):
    event_class = PullRequestApproved

    def handle(self, event: PullRequestApproved) -> None:
        handler = container.get(MergePullRequestCommandHandler)

        handler(MergePullRequestCommand(slice_id=event.slice_id.value))

from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.address_review_changes import (
    AddressReviewChangesCommand,
    AddressReviewChangesCommandHandler,
)
from grooveloop.delivery.domain.events import ReviewChangesRequested
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo


class AddressReviewChangesWhenReviewChangesRequested(EventHandler[ReviewChangesRequested]):
    event_class = ReviewChangesRequested

    def handle(self, event: ReviewChangesRequested) -> None:
        handler = container.get(AddressReviewChangesCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)

        handler(AddressReviewChangesCommand(slice_id=event.slice_id.value, workdir=workdir.value, repo=repo.value))

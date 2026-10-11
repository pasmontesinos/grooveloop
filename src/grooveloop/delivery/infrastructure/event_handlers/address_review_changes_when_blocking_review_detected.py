from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.address_review_changes import (
    AddressReviewChangesCommand,
    AddressReviewChangesCommandHandler,
)
from grooveloop.delivery.domain.events import BlockingReviewDetected
from grooveloop.delivery.infrastructure.max_review_rounds import MaxReviewRounds
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo


class AddressReviewChangesWhenBlockingReviewDetected(EventHandler[BlockingReviewDetected]):
    event_class = BlockingReviewDetected

    def handle(self, event: BlockingReviewDetected) -> None:
        handler = container.get(AddressReviewChangesCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)
        max_review_rounds = container.get(MaxReviewRounds)

        handler(
            AddressReviewChangesCommand(
                slice_id=event.slice_id.value,
                workdir=workdir.value,
                repo=repo.value,
                automatic=True,
                max_review_rounds=max_review_rounds.value,
            )
        )

from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.review_pull_request import (
    ReviewPullRequestCommand,
    ReviewPullRequestCommandHandler,
)
from grooveloop.delivery.domain.events import ReReviewRequired
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo


class ReviewPullRequestWhenReReviewRequired(EventHandler[ReReviewRequired]):
    event_class = ReReviewRequired

    def handle(self, event: ReReviewRequired) -> None:
        handler = container.get(ReviewPullRequestCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)
        journal_enabled = container.get(JournalEnabled)

        handler(
            ReviewPullRequestCommand(
                slice_id=event.slice_id.value,
                pull_request_number=event.pull_request_number.value,
                workdir=workdir.value,
                repo=repo.value,
                journal_enabled=journal_enabled.value,
            )
        )

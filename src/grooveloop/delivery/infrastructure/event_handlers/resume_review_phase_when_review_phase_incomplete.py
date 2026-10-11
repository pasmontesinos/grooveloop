from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.resume_review_phase import (
    ResumeReviewPhaseCommand,
    ResumeReviewPhaseCommandHandler,
)
from grooveloop.delivery.domain.events import ReviewPhaseIncomplete
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo


class ResumeReviewPhaseWhenReviewPhaseIncomplete(EventHandler[ReviewPhaseIncomplete]):
    event_class = ReviewPhaseIncomplete

    def handle(self, event: ReviewPhaseIncomplete) -> None:
        handler = container.get(ResumeReviewPhaseCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)
        max_retries = container.get(MaxRetries)
        journal_enabled = container.get(JournalEnabled)

        handler(
            ResumeReviewPhaseCommand(
                slice_id=event.slice_id.value,
                run_id=event.run_id,
                workdir=workdir.value,
                repo=repo.value,
                max_retries=max_retries.value,
                journal_enabled=journal_enabled.value,
            )
        )

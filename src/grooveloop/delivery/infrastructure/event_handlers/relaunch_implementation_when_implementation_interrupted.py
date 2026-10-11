from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.relaunch_implementation import (
    RelaunchImplementationCommand,
    RelaunchImplementationCommandHandler,
)
from grooveloop.delivery.domain.events import ImplementationInterrupted
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo


class RelaunchImplementationWhenImplementationInterrupted(EventHandler[ImplementationInterrupted]):
    event_class = ImplementationInterrupted

    def handle(self, event: ImplementationInterrupted) -> None:
        handler = container.get(RelaunchImplementationCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)
        max_retries = container.get(MaxRetries)
        journal_enabled = container.get(JournalEnabled)

        handler(
            RelaunchImplementationCommand(
                slice_id=event.slice_id.value,
                run_id=event.run_id,
                workdir=workdir.value,
                repo=repo.value,
                max_retries=max_retries.value,
                journal_enabled=journal_enabled.value,
            )
        )

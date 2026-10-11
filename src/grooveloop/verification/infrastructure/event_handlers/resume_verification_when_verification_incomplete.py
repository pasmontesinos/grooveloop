from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.verification.application.commands.resume_verification import (
    ResumeVerificationCommand,
    ResumeVerificationCommandHandler,
)
from grooveloop.verification.domain.events import VerificationIncomplete


class ResumeVerificationWhenVerificationIncomplete(EventHandler[VerificationIncomplete]):
    event_class = VerificationIncomplete

    def handle(self, event: VerificationIncomplete) -> None:
        handler = container.get(ResumeVerificationCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)
        max_retries = container.get(MaxRetries)

        handler(
            ResumeVerificationCommand(
                slice_id=event.slice_id.value,
                run_id=event.run_id,
                pull_request_number=event.pull_request_number.value,
                title=event.title,
                description=event.description,
                workdir=workdir.value,
                repo=repo.value,
                max_retries=max_retries.value,
            )
        )

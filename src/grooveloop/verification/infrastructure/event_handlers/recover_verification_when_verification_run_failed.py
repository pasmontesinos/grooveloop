from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.verification.application.commands.recover_verification import (
    RecoverVerificationCommand,
    RecoverVerificationCommandHandler,
)
from grooveloop.verification.domain.events import VerificationRunFailed


class RecoverVerificationWhenVerificationRunFailed(EventHandler[VerificationRunFailed]):
    event_class = VerificationRunFailed

    def handle(self, event: VerificationRunFailed) -> None:
        handler = container.get(RecoverVerificationCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)
        max_retries = container.get(MaxRetries)

        handler(
            RecoverVerificationCommand(
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

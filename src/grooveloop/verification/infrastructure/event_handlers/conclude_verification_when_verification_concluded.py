from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.verification.application.commands.conclude_verification import (
    ConcludeVerificationCommand,
    ConcludeVerificationCommandHandler,
)
from grooveloop.verification.domain.events import VerificationConcluded


class ConcludeVerificationWhenVerificationConcluded(EventHandler[VerificationConcluded]):
    event_class = VerificationConcluded

    def handle(self, event: VerificationConcluded) -> None:
        handler = container.get(ConcludeVerificationCommandHandler)

        handler(ConcludeVerificationCommand(slice_id=event.slice_id.value))

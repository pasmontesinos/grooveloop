from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.verification.domain.slice_id import SliceId

if TYPE_CHECKING:
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository


@dataclass(frozen=True)
class ConcludeVerificationCommand(Command):
    slice_id: str


class ConcludeVerificationCommandHandler(CommandHandler[ConcludeVerificationCommand, None]):
    def __init__(self, slice_verification_repository: SliceVerificationRepository) -> None:
        self._slice_verification_repository = slice_verification_repository

    def __call__(self, command: ConcludeVerificationCommand) -> None:
        verification = self._slice_verification_repository.find(SliceId(command.slice_id))
        if verification is None or not verification.can_conclude():
            return

        verification.conclude()

        self._slice_verification_repository.save(verification)

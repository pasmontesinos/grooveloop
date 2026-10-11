from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice_repository import SliceRepository


@dataclass(frozen=True)
class CompleteReviewCommand(Command):
    slice_id: str


class CompleteReviewCommandHandler(CommandHandler[CompleteReviewCommand, None]):
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def __call__(self, command: CompleteReviewCommand) -> None:
        a_slice = self._slice_repository.find(SliceId(command.slice_id))
        if a_slice is None or not a_slice.can_complete_review():
            return

        a_slice.complete_review()

        self._slice_repository.save(a_slice)

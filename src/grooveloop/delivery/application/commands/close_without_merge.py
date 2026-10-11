from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice_repository import SliceRepository


@dataclass(frozen=True)
class CloseWithoutMergeCommand(Command):
    slice_id: str


class CloseWithoutMergeCommandHandler(CommandHandler[CloseWithoutMergeCommand, None]):
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def __call__(self, command: CloseWithoutMergeCommand) -> None:
        a_slice = self._slice_repository.find(SliceId(command.slice_id))
        if a_slice is None or not a_slice.can_be_closed_without_merge():
            return

        a_slice.close_without_merge()
        self._slice_repository.save(a_slice)

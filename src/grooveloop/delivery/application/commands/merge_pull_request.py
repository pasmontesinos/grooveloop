from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.mergeability import Mergeability
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.delivery.domain.pull_request_merger import PullRequestMerger
    from grooveloop.delivery.domain.slice_repository import SliceRepository


@dataclass(frozen=True)
class MergePullRequestCommand(Command):
    slice_id: str


class MergePullRequestCommandHandler(CommandHandler[MergePullRequestCommand, None]):
    def __init__(self, slice_repository: SliceRepository, pull_request_merger: PullRequestMerger) -> None:
        self._slice_repository = slice_repository
        self._pull_request_merger = pull_request_merger

    def __call__(self, command: MergePullRequestCommand) -> None:
        a_slice = self._slice_repository.find(SliceId(command.slice_id))
        if a_slice is None or not a_slice.is_auto_mergeable():
            return

        number = a_slice.pull_request_number
        if number is None or self._pull_request_merger.mergeability(number) is not Mergeability.CLEAN:
            return

        self._pull_request_merger.merge(number)

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.delivery.application.services.agent_run_failure_cause import AgentRunFailureCause
    from grooveloop.delivery.domain.slice_repository import SliceRepository


@dataclass(frozen=True)
class FailDispatchedSliceCommand(Command):
    slice_id: str


class FailDispatchedSliceCommandHandler(CommandHandler[FailDispatchedSliceCommand, None]):
    def __init__(self, slice_repository: SliceRepository, agent_run_failure_cause: AgentRunFailureCause) -> None:
        self._slice_repository = slice_repository
        self._failure_cause = agent_run_failure_cause

    def __call__(self, command: FailDispatchedSliceCommand) -> None:
        a_slice = self._slice_repository.find(SliceId(command.slice_id))
        if a_slice is None or not (a_slice.is_implementing() or a_slice.is_under_review()):
            return

        a_slice.fail(self._failure_cause.of(a_slice.agent_run_id))
        self._slice_repository.save(a_slice)

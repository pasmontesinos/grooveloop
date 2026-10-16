from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.shared.domain.agent_task_type import AgentTaskType

if TYPE_CHECKING:
    from grooveloop.delivery.application.tasks.addressing_task import AddressingTask
    from grooveloop.delivery.domain.directive_marker import DirectiveMarker
    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.shared.domain.agent_profiles import AgentProfiles
    from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry

_DEVELOPER_PROFILE = "developer"


@dataclass(frozen=True)
class AddressReviewChangesCommand(Command):
    slice_id: str
    workdir: str
    repo: str
    automatic: bool = False
    max_review_rounds: int = 0


class AddressReviewChangesCommandHandler(CommandHandler[AddressReviewChangesCommand, None]):
    def __init__(
        self,
        slice_repository: SliceRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        addressing_task: AddressingTask,
        directive_marker: DirectiveMarker,
    ) -> None:
        self._slice_repository = slice_repository
        self._agent_runner_registry = agent_runner_registry
        self._agent_profiles = agent_profiles
        self._addressing_task = addressing_task
        self._directive_marker = directive_marker

    def __call__(self, command: AddressReviewChangesCommand) -> None:
        a_slice = self._slice_repository.find(SliceId(command.slice_id))
        if a_slice is None or not a_slice.can_address_changes(command.automatic, command.max_review_rounds):
            return

        profile = self._agent_profiles.find(_DEVELOPER_PROFILE)
        if profile is None:
            return

        if not command.automatic:
            self._directive_marker.mark(a_slice.addressed_directives_without_mark(), DirectiveMark.ADDRESSED)
            self._directive_marker.mark(a_slice.pending_directives(), DirectiveMark.TAKEN)

        task = self._addressing_task.build(a_slice, automatic=command.automatic)
        run = self._agent_runner_registry.runner_for(profile.engine).dispatch(
            profile.render(task),
            command.workdir,
            AgentTaskType.ADDRESS_REVIEW,
            slice_id=a_slice.id.value,
            repo=command.repo,
            model=profile.model,
        )
        a_slice.record_agent_run(run)
        if command.automatic:
            a_slice.consume_review_round()
        else:
            a_slice.clear_review_rounds()

        a_slice.request_changes()

        self._slice_repository.save(a_slice)

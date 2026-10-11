from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.parallel_slice_limit import ParallelSliceLimit
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.shared.domain.agent_task_type import AgentTaskType

if TYPE_CHECKING:
    from grooveloop.delivery.application.tasks.implementation_task import ImplementationTask
    from grooveloop.delivery.domain.slice_labels import SliceLabels
    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.shared.domain.agent_profiles import AgentProfiles
    from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry

_DEVELOPER_PROFILE = "developer"


@dataclass(frozen=True)
class DispatchSliceCommand(Command):
    slice_id: str
    workdir: str
    repo: str
    max_parallel_slices: int = 1
    journal_enabled: bool = False


class DispatchSliceCommandHandler(CommandHandler[DispatchSliceCommand, None]):
    def __init__(
        self,
        slice_repository: SliceRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        slice_labels: SliceLabels,
        implementation_task: ImplementationTask,
    ) -> None:
        self._slice_repository = slice_repository
        self._agent_runner_registry = agent_runner_registry
        self._agent_profiles = agent_profiles
        self._slice_labels = slice_labels
        self._implementation_task = implementation_task

    def __call__(self, command: DispatchSliceCommand) -> None:
        a_slice = self._slice_repository.find(SliceId(command.slice_id))
        if a_slice is None or not a_slice.can_be_dispatched():
            return

        if a_slice.story_id is None:
            return

        story_slices = self._slice_repository.search(story_id=a_slice.story_id, open=True)
        if ParallelSliceLimit(command.max_parallel_slices).is_reached_by(story_slices):
            return

        profile = self._agent_profiles.find(_DEVELOPER_PROFILE)
        if profile is None:
            return

        task = self._implementation_task.build(a_slice, command.repo, command.journal_enabled)
        self._slice_labels.ensure(a_slice.id)
        run = self._agent_runner_registry.runner_for(profile.engine).dispatch(
            profile.render(task),
            command.workdir,
            AgentTaskType.IMPLEMENT_SLICE,
            slice_id=a_slice.id.value,
            repo=command.repo,
            model=profile.model,
            story_id=a_slice.story_id.value,
            profile=profile.name,
        )
        a_slice.record_agent_run(run)
        a_slice.dispatch()

        self._slice_repository.save(a_slice)

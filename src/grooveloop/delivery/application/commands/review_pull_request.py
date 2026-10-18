from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.shared.domain.agent_task_type import AgentTaskType

if TYPE_CHECKING:
    from grooveloop.delivery.application.tasks.review_task import ReviewTask
    from grooveloop.delivery.domain.directive_marker import DirectiveMarker
    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.shared.domain.agent_profiles import AgentProfiles
    from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry

_REVIEWER_PROFILE = "reviewer"


@dataclass(frozen=True)
class ReviewPullRequestCommand(Command):
    slice_id: str
    pull_request_number: int
    workdir: str
    repo: str
    journal_enabled: bool = False


class ReviewPullRequestCommandHandler(CommandHandler[ReviewPullRequestCommand, None]):
    def __init__(
        self,
        slice_repository: SliceRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        review_task: ReviewTask,
        directive_marker: DirectiveMarker,
    ) -> None:
        self._slice_repository = slice_repository
        self._agent_runner_registry = agent_runner_registry
        self._agent_profiles = agent_profiles
        self._review_task = review_task
        self._directive_marker = directive_marker

    def __call__(self, command: ReviewPullRequestCommand) -> None:
        a_slice = self._slice_repository.find(SliceId(command.slice_id))
        if a_slice is None or not a_slice.can_start_review():
            return

        profile = self._agent_profiles.find(_REVIEWER_PROFILE)
        if profile is None:
            return

        if a_slice.is_addressing_changes():
            self._directive_marker.mark(a_slice.taken_directives(), DirectiveMark.ADDRESSED)

        if a_slice.pull_request is None:
            a_slice.anchor_pull_request(PullRequestNumber(command.pull_request_number))
            pull_request_number = command.pull_request_number
        else:
            pull_request_number = a_slice.pull_request.number.value

        task = self._review_task.build(a_slice, pull_request_number, command.repo, command.journal_enabled)
        run = self._agent_runner_registry.runner_for(profile.engine).dispatch(
            profile.render(task),
            command.workdir,
            AgentTaskType.REVIEW_SLICE,
            slice_id=a_slice.id.value,
            repo=command.repo,
            model=profile.model,
            story_id=a_slice.story_id.value if a_slice.story_id is not None else None,
            profile=profile.name,
        )
        a_slice.record_agent_run(run)
        a_slice.start_review()

        self._slice_repository.save(a_slice)

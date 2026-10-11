from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from grooveloop.learning.domain.lesson import Lesson
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.shared.domain.agent_task_type import AgentTaskType

if TYPE_CHECKING:
    from grooveloop.learning.application.tasks.refinement_task import RefinementTask
    from grooveloop.learning.domain.lesson_repository import LessonRepository
    from grooveloop.shared.domain.agent_profiles import AgentProfiles
    from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry

_SCRIBE_PROFILE = "scribe"


class RefineConventionsComment(TypedDict):
    body: str
    path: str
    line: int
    diff_hunk: str


@dataclass(frozen=True)
class RefineConventionsCommand(Command):
    source_pull_request: int
    story_id: str
    comments: list[RefineConventionsComment]
    workdir: str
    repo: str


class RefineConventionsCommandHandler(CommandHandler[RefineConventionsCommand, None]):
    def __init__(
        self,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        lesson_repository: LessonRepository,
        refinement_task: RefinementTask,
    ) -> None:
        self._agent_runner_registry = agent_runner_registry
        self._agent_profiles = agent_profiles
        self._lesson_repository = lesson_repository
        self._refinement_task = refinement_task

    def __call__(self, command: RefineConventionsCommand) -> None:
        source_pull_request = SourcePullRequest(command.source_pull_request)
        if self._lesson_repository.find_by_source_pull_request(source_pull_request) is not None:
            return

        profile = self._agent_profiles.find(_SCRIBE_PROFILE)
        if profile is None:
            return

        comments = [LessonComment(**comment) for comment in command.comments]

        self._agent_runner_registry.runner_for(profile.engine).dispatch(
            profile.render(self._refinement_task.build(command.source_pull_request, comments)),
            command.workdir,
            AgentTaskType.REFINE_CONVENTIONS,
            slice_id=str(command.source_pull_request),
            repo=command.repo,
            model=profile.model,
        )

        self._lesson_repository.save(Lesson.create(source_pull_request, StoryId(command.story_id), comments))

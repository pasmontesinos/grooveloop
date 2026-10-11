from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.verification.domain.slice_id import SliceId

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_profiles import AgentProfiles
    from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
    from grooveloop.verification.application.tasks.verification_task import VerificationTask
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository

_VERIFIER_PROFILE = "verifier"


@dataclass(frozen=True)
class VerifyDeploymentCommand(Command):
    slice_id: str
    pull_request_number: int
    title: str
    description: str
    workdir: str
    repo: str


class VerifyDeploymentCommandHandler(CommandHandler[VerifyDeploymentCommand, None]):
    def __init__(
        self,
        slice_verification_repository: SliceVerificationRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        verification_task: VerificationTask,
    ) -> None:
        self._slice_verification_repository = slice_verification_repository
        self._agent_runner_registry = agent_runner_registry
        self._agent_profiles = agent_profiles
        self._verification_task = verification_task

    def __call__(self, command: VerifyDeploymentCommand) -> None:
        verification = self._slice_verification_repository.find(SliceId(command.slice_id))
        if verification is None or not verification.can_start():
            return

        profile = self._agent_profiles.find(_VERIFIER_PROFILE)
        if profile is None:
            return

        run = self._agent_runner_registry.runner_for(profile.engine).dispatch(
            profile.render(
                self._verification_task.build(
                    command.pull_request_number, command.title, command.description, command.repo
                )
            ),
            command.workdir,
            AgentTaskType.VERIFY_DEPLOY,
            slice_id=command.slice_id,
            repo=command.repo,
            model=profile.model,
        )
        verification.record_agent_run(run)
        verification.start()

        self._slice_verification_repository.save(verification)

from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_task_type import AgentTaskType

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_profiles import AgentProfiles
    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
    from grooveloop.verification.application.tasks.verification_task import VerificationTask
    from grooveloop.verification.domain.slice_verification import SliceVerification

_VERIFIER_PROFILE = "verifier"


class VerificationRecovery:
    def __init__(
        self,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        verification_task: VerificationTask,
    ) -> None:
        self._agent_runner_registry = agent_runner_registry
        self._agent_profiles = agent_profiles
        self._verification_task = verification_task

    def awaits_recovery(self, verification: SliceVerification, run_id: str) -> bool:
        return verification.is_running() and verification.agent_run_id == run_id

    def resumption(self, pull_request_number: int) -> str:
        return self._verification_task.resumption(pull_request_number)

    def redispatch(
        self, slice_id: str, pull_request_number: int, title: str, description: str, workdir: str, repo: str
    ) -> AgentRun | None:
        profile = self._agent_profiles.find(_VERIFIER_PROFILE)
        if profile is None:
            return None

        task = self._verification_task.build(pull_request_number, title, description, repo)

        return self._agent_runner_registry.runner_for(profile.engine).dispatch(
            profile.render(task),
            workdir,
            AgentTaskType.VERIFY_DEPLOY,
            slice_id=slice_id,
            repo=repo,
            model=profile.model,
        )

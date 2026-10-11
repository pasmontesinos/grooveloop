from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_task_type import AgentTaskType

if TYPE_CHECKING:
    from grooveloop.delivery.application.tasks.implementation_task import ImplementationTask
    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.shared.domain.agent_profiles import AgentProfiles
    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.shared.domain.agent_runner import AgentRunner
    from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry

_DEVELOPER_PROFILE = "developer"


class ImplementationRecovery:
    def __init__(
        self,
        agent_runner: AgentRunner,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        implementation_task: ImplementationTask,
    ) -> None:
        self._agent_runner = agent_runner
        self._agent_runner_registry = agent_runner_registry
        self._agent_profiles = agent_profiles
        self._implementation_task = implementation_task

    def awaits_recovery(self, a_slice: Slice, run_id: str) -> bool:
        return (
            a_slice.is_implementing()
            and a_slice.pull_request is None
            and a_slice.agent_run_id == run_id
            and a_slice.story_id is not None
        )

    def resumption(self, a_slice: Slice) -> str:
        return self._implementation_task.resumption(a_slice)

    def redispatch(
        self, a_slice: Slice, previous_run_id: str, workdir: str, repo: str, journal_enabled: bool
    ) -> AgentRun | None:
        assert a_slice.story_id is not None
        profile = self._agent_profiles.find(_DEVELOPER_PROFILE)
        if profile is None:
            return None

        previous_branch = self._agent_runner.pushed_branch_of(previous_run_id)
        task = self._implementation_task.build(a_slice, repo, journal_enabled, previous_branch)

        return self._agent_runner_registry.runner_for(profile.engine).dispatch(
            profile.render(task),
            workdir,
            AgentTaskType.IMPLEMENT_SLICE,
            slice_id=a_slice.id.value,
            repo=repo,
            model=profile.model,
            story_id=a_slice.story_id.value,
            profile=profile.name,
        )

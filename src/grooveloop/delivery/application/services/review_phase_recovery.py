from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_task_type import AgentTaskType

if TYPE_CHECKING:
    from grooveloop.delivery.application.tasks.addressing_task import AddressingTask
    from grooveloop.delivery.application.tasks.review_task import ReviewTask
    from grooveloop.delivery.domain.pull_request import PullRequest
    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.shared.domain.agent_profiles import AgentProfiles
    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry

_REVIEWER_PROFILE = "reviewer"
_DEVELOPER_PROFILE = "developer"


class ReviewPhaseRecovery:
    def __init__(
        self,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        review_task: ReviewTask,
        addressing_task: AddressingTask,
    ) -> None:
        self._agent_runner_registry = agent_runner_registry
        self._agent_profiles = agent_profiles
        self._review_task = review_task
        self._addressing_task = addressing_task

    def awaits_recovery(self, a_slice: Slice, run_id: str) -> bool:
        return a_slice.is_in_review_phase() and a_slice.pull_request is not None and a_slice.agent_run_id == run_id

    def resumption(self, a_slice: Slice) -> str:
        assert a_slice.pull_request is not None
        if a_slice.is_under_review():
            return self._review_task.resumption(a_slice, a_slice.pull_request.number.value)

        return self._addressing_task.resumption(a_slice)

    def redispatch(self, a_slice: Slice, workdir: str, repo: str, journal_enabled: bool) -> AgentRun | None:
        assert a_slice.pull_request is not None
        profile_name, task_type, task = self._phase_task(a_slice, a_slice.pull_request, repo, journal_enabled)
        profile = self._agent_profiles.find(profile_name)
        if profile is None:
            return None

        return self._agent_runner_registry.runner_for(profile.engine).dispatch(
            profile.render(task),
            workdir,
            task_type,
            slice_id=a_slice.id.value,
            repo=repo,
            model=profile.model,
            story_id=a_slice.story_id.value if a_slice.story_id is not None else None,
            profile=profile.name,
        )

    def _phase_task(
        self, a_slice: Slice, pull_request: PullRequest, repo: str, journal_enabled: bool
    ) -> tuple[str, AgentTaskType, str]:
        if a_slice.is_under_review():
            task = self._review_task.build(a_slice, pull_request.number.value, repo, journal_enabled)

            return _REVIEWER_PROFILE, AgentTaskType.REVIEW_SLICE, task

        task = self._addressing_task.build(a_slice, automatic=a_slice.review_rounds > 0)

        return _DEVELOPER_PROFILE, AgentTaskType.ADDRESS_REVIEW, task

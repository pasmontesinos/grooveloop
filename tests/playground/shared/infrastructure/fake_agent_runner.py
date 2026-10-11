from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run import AgentRun
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.domain.agent_runner import AgentRunner

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_task_type import AgentTaskType


class FakeAgentRunner(AgentRunner):
    def __init__(
        self,
        outcome: AgentOutcome = AgentOutcome.RUNNING,
        verdict: AgentRunVerdict | None = None,
        pushed_branch: str | None = None,
        resumable: bool = False,
    ) -> None:
        self.dispatched_count = 0
        self.last_instruction = ""
        self.last_workdir = ""
        self.last_task_type: AgentTaskType | None = None
        self.last_slice_id = ""
        self.last_repo = ""
        self.last_model = ""
        self.last_story_id: str | None = None
        self.last_profile: str | None = None
        self._outcome = verdict.outcome if verdict is not None else outcome
        self._verdict = verdict or AgentRunVerdict(outcome)
        self._pushed_branch = pushed_branch
        self._resumable = resumable
        self.resumed_count = 0
        self.last_resumed_run_id = ""
        self.last_resume_instruction = ""

    def dispatch(
        self,
        instruction: str,
        workdir: str,
        task_type: AgentTaskType,
        slice_id: str,
        repo: str,
        model: str,
        story_id: str | None = None,
        profile: str | None = None,
    ) -> AgentRun:
        self.dispatched_count += 1
        self.last_instruction = instruction
        self.last_workdir = workdir
        self.last_task_type = task_type
        self.last_slice_id = slice_id
        self.last_repo = repo
        self.last_model = model
        self.last_story_id = story_id
        self.last_profile = profile

        return AgentRun(run_id="fake-run", pid=0)

    def resume(self, previous_run_id: str, instruction: str) -> AgentRun | None:
        if not self._resumable:
            return None

        self.resumed_count += 1
        self.last_resumed_run_id = previous_run_id
        self.last_resume_instruction = instruction

        return AgentRun(run_id="resumed-run", pid=0)

    def outcome_of(self, run_id: str) -> AgentOutcome:
        return self._outcome

    def verdict_of(self, run_id: str) -> AgentRunVerdict:
        return self._verdict

    def pushed_branch_of(self, run_id: str) -> str | None:
        return self._pushed_branch


class FailingAgentRunner(FakeAgentRunner):
    def __init__(self, failing_slice_id: str | None = None, verdict: AgentRunVerdict | None = None) -> None:
        super().__init__(verdict=verdict)
        self._failing_slice_id = failing_slice_id

    def dispatch(
        self,
        instruction: str,
        workdir: str,
        task_type: AgentTaskType,
        slice_id: str,
        repo: str,
        model: str,
        story_id: str | None = None,
        profile: str | None = None,
    ) -> AgentRun:
        if self._failing_slice_id in (None, slice_id):
            raise RuntimeError("git fetch failed")

        return super().dispatch(instruction, workdir, task_type, slice_id, repo, model, story_id, profile)

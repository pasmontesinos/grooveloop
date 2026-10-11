from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_outcome import AgentOutcome
    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
    from grooveloop.shared.domain.agent_task_type import AgentTaskType


class AgentRunner(ABC):
    @abstractmethod
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
    ) -> AgentRun: ...

    @abstractmethod
    def resume(self, previous_run_id: str, instruction: str) -> AgentRun | None: ...

    @abstractmethod
    def outcome_of(self, run_id: str) -> AgentOutcome: ...

    @abstractmethod
    def verdict_of(self, run_id: str) -> AgentRunVerdict: ...

    @abstractmethod
    def pushed_branch_of(self, run_id: str) -> str | None: ...

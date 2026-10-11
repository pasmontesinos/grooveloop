from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import AgentRunAbandoned

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns
    from grooveloop.shared.infrastructure.target_repo import TargetRepo


class AgentRunAbandonedDetector:
    def __init__(self, abandoned_agent_runs: AbandonedAgentRuns, target_repo: TargetRepo) -> None:
        self._abandoned_agent_runs = abandoned_agent_runs
        self._target_repo = target_repo

    def detect(self) -> Iterator[AgentRunAbandoned]:
        for run_id in self._abandoned_agent_runs.abandoned_run_ids(self._target_repo.value):
            yield AgentRunAbandoned(run_id=run_id)

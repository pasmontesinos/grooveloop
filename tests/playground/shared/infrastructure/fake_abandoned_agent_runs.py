from __future__ import annotations

from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns


class FakeAbandonedAgentRuns(AbandonedAgentRuns):
    def __init__(self, run_ids_by_repo: dict[str, list[str]] | None = None) -> None:
        self._run_ids_by_repo = {repo: list(run_ids) for repo, run_ids in (run_ids_by_repo or {}).items()}
        self.closed: list[str] = []

    def abandoned_run_ids(self, repo: str) -> list[str]:
        return list(self._run_ids_by_repo.get(repo, []))

    def close(self, run_id: str) -> None:
        self.closed.append(run_id)
        for run_ids in self._run_ids_by_repo.values():
            if run_id in run_ids:
                run_ids.remove(run_id)


class FailingAbandonedAgentRuns(FakeAbandonedAgentRuns):
    def __init__(self, run_ids_by_repo: dict[str, list[str]], failing_run_id: str) -> None:
        super().__init__(run_ids_by_repo)
        self._failing_run_id = failing_run_id

    def close(self, run_id: str) -> None:
        if run_id == self._failing_run_id:
            raise OSError("read-only run dir")

        super().close(run_id)

from __future__ import annotations

from grooveloop.shared.domain.agent_workspaces import AgentWorkspaces


class FakeAgentWorkspaces(AgentWorkspaces):
    def __init__(self, run_ids: list[str] | None = None) -> None:
        self._run_ids = list(run_ids or [])
        self.removed: list[str] = []

    def finished_run_ids(self) -> list[str]:
        return list(self._run_ids)

    def workspace_of(self, run_id: str) -> str | None:
        if run_id not in self._run_ids:
            return None

        return f"/runs/{run_id}/workdir"

    def remove(self, run_id: str) -> None:
        self.removed.append(run_id)
        if run_id in self._run_ids:
            self._run_ids.remove(run_id)


class FailingAgentWorkspaces(FakeAgentWorkspaces):
    def __init__(self, run_ids: list[str], failing_run_id: str) -> None:
        super().__init__(run_ids)
        self._failing_run_id = failing_run_id

    def remove(self, run_id: str) -> None:
        if run_id == self._failing_run_id:
            raise OSError("read-only run dir")

        super().remove(run_id)

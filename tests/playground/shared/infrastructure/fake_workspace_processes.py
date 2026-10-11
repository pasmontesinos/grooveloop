from __future__ import annotations

from grooveloop.shared.domain.workspace_processes import WorkspaceProcesses


class FakeWorkspaceProcesses(WorkspaceProcesses):
    def __init__(self, failure: Exception | None = None) -> None:
        self._failure = failure
        self.terminated: list[str] = []

    def terminate(self, workspace: str) -> None:
        if self._failure is not None:
            raise self._failure

        self.terminated.append(workspace)

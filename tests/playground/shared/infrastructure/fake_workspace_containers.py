from __future__ import annotations

from grooveloop.shared.domain.workspace_containers import WorkspaceContainers


class FakeWorkspaceContainers(WorkspaceContainers):
    def __init__(self, failure: Exception | None = None) -> None:
        self._failure = failure
        self.removed: list[str] = []

    def remove(self, workspace: str) -> None:
        if self._failure is not None:
            raise self._failure

        self.removed.append(workspace)

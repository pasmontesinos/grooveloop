from __future__ import annotations

from abc import ABC, abstractmethod


class WorkspaceProcesses(ABC):
    @abstractmethod
    def terminate(self, workspace: str) -> None: ...

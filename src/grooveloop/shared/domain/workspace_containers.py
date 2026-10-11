from __future__ import annotations

from abc import ABC, abstractmethod


class WorkspaceContainers(ABC):
    @abstractmethod
    def remove(self, workspace: str) -> None: ...

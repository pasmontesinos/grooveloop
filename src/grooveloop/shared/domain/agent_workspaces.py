from __future__ import annotations

from abc import ABC, abstractmethod


class AgentWorkspaces(ABC):
    @abstractmethod
    def finished_run_ids(self) -> list[str]: ...

    @abstractmethod
    def workspace_of(self, run_id: str) -> str | None: ...

    @abstractmethod
    def remove(self, run_id: str) -> None: ...

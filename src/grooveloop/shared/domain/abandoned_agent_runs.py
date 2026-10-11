from __future__ import annotations

from abc import ABC, abstractmethod


class AbandonedAgentRuns(ABC):
    @abstractmethod
    def abandoned_run_ids(self, repo: str) -> list[str]: ...

    @abstractmethod
    def close(self, run_id: str) -> None: ...

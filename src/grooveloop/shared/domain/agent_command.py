from __future__ import annotations

from abc import ABC, abstractmethod


class AgentCommand(ABC):
    @property
    @abstractmethod
    def engine(self) -> str: ...

    @abstractmethod
    def argv(self, model: str) -> list[str]: ...

    @abstractmethod
    def resume_argv(self, model: str, log_head: str) -> list[str] | None: ...

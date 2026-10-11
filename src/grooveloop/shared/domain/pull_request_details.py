from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.pull_request_detail import PullRequestDetail
    from grooveloop.shared.domain.pull_request_detail_reading import PullRequestDetailReading


class PullRequestDetails(ABC):
    @abstractmethod
    def publish(self, repo: str, detail: PullRequestDetail) -> None: ...

    @abstractmethod
    def find(self, repo: str, number: int) -> PullRequestDetail | None: ...

    @abstractmethod
    def read(self, repo: str, number: int) -> PullRequestDetailReading: ...

    @abstractmethod
    def retain(self, repo: str, numbers: list[int]) -> None: ...

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.domain.mergeability import Mergeability
    from grooveloop.delivery.domain.pull_request_number import PullRequestNumber


class PullRequestMerger(ABC):
    @abstractmethod
    def mergeability(self, number: PullRequestNumber) -> Mergeability: ...

    @abstractmethod
    def merge(self, number: PullRequestNumber) -> None: ...

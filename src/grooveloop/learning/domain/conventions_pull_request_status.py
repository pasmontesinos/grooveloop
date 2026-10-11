from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest


class ConventionsPullRequestStatus(ABC):
    @abstractmethod
    def is_open(self, conventions_pull_request: ConventionsPullRequest) -> bool: ...

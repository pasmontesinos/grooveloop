from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.learning.domain.refinement_outcome import RefinementOutcome
    from grooveloop.learning.domain.source_pull_request import SourcePullRequest


class RefinementResult(ABC):
    @abstractmethod
    def of(self, source_pull_request: SourcePullRequest, since: datetime) -> RefinementOutcome | None: ...

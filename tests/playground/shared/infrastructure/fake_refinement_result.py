from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.refinement_result import RefinementResult

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.learning.domain.refinement_outcome import RefinementOutcome
    from grooveloop.learning.domain.source_pull_request import SourcePullRequest


class FakeRefinementResult(RefinementResult):
    def __init__(self, outcomes: dict[int, RefinementOutcome] | None = None) -> None:
        self._outcomes = dict(outcomes or {})
        self.asked: list[tuple[int, datetime]] = []

    def of(self, source_pull_request: SourcePullRequest, since: datetime) -> RefinementOutcome | None:
        self.asked.append((source_pull_request.value, since))

        return self._outcomes.get(source_pull_request.value)

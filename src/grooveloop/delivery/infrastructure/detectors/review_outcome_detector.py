from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import BlockingReviewDetected, HumanDecisionRequired, ReviewCompleted
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.shared.domain.agent_outcome import AgentOutcome

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.delivery.infrastructure.max_review_rounds import MaxReviewRounds
    from grooveloop.shared.domain.agent_runner import AgentRunner


class ReviewOutcomeDetector:
    def __init__(
        self,
        slice_repository: SliceRepository,
        agent_runner: AgentRunner,
        max_review_rounds: MaxReviewRounds,
    ) -> None:
        self._slice_repository = slice_repository
        self._agent_runner = agent_runner
        self._max_review_rounds = max_review_rounds

    def detect(self) -> Iterator[ReviewCompleted | HumanDecisionRequired | BlockingReviewDetected]:
        for a_slice in self._slice_repository.search(status=SliceStatus.UNDER_REVIEW, open=True):
            if a_slice.needs_a_human_decision():
                yield HumanDecisionRequired(slice_id=a_slice.id)
            elif a_slice.deserves_a_correction(self._max_review_rounds.value):
                yield BlockingReviewDetected(slice_id=a_slice.id)
            elif self._review_is_over(a_slice):
                yield ReviewCompleted(slice_id=a_slice.id)

    def _review_is_over(self, a_slice: Slice) -> bool:
        if a_slice.awaits_its_review_summary(self._max_review_rounds.value) and self._reviewer_is_still_running(
            a_slice
        ):
            return False

        return a_slice.has_a_review_outcome()

    def _reviewer_is_still_running(self, a_slice: Slice) -> bool:
        run_id = a_slice.agent_run_id

        return run_id is not None and self._agent_runner.outcome_of(run_id) == AgentOutcome.RUNNING

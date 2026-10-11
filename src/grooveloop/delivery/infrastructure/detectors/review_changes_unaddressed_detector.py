from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.events import ReviewChangesUnaddressed
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.shared.domain.agent_outcome import AgentOutcome

if TYPE_CHECKING:
    from collections.abc import Iterator

    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.shared.domain.agent_runner import AgentRunner


class ReviewChangesUnaddressedDetector:
    def __init__(self, slice_repository: SliceRepository, agent_runner: AgentRunner) -> None:
        self._slice_repository = slice_repository
        self._agent_runner = agent_runner

    def detect(self) -> Iterator[ReviewChangesUnaddressed]:
        for a_slice in self._slice_repository.search(status=SliceStatus.CHANGES_REQUESTED, open=True):
            run_id = a_slice.agent_run_id
            if (
                run_id is not None
                and a_slice.lacks_commits_after_review()
                and self._agent_runner.outcome_of(run_id) is AgentOutcome.FAILED
            ):
                yield ReviewChangesUnaddressed(slice_id=a_slice.id)

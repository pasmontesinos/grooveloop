from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.retry_policy import RetryPolicy

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.shared.domain.agent_run_cause import AgentRunCause
    from grooveloop.shared.domain.clock import Clock


class SliceRetry:
    def __init__(self, slice_repository: SliceRepository, clock: Clock) -> None:
        self._slice_repository = slice_repository
        self._clock = clock

    def attempt(
        self,
        a_slice: Slice,
        finished_at: datetime,
        max_retries: int,
        exhausted_cause: AgentRunCause,
        relaunch: Callable[[], AgentRun | None],
    ) -> None:
        policy = RetryPolicy(max_retries)
        if not policy.has_budget(a_slice.retries):
            a_slice.fail(exhausted_cause)
            self._slice_repository.save(a_slice)

            return

        if not policy.is_due(a_slice.retries, finished_at, self._clock.now()):
            return

        run = relaunch()
        if run is None:
            return

        a_slice.retry_agent_run(run)

        self._slice_repository.save(a_slice)

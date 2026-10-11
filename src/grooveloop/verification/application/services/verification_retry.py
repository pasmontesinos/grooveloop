from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.retry_policy import RetryPolicy

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.shared.domain.agent_run_cause import AgentRunCause
    from grooveloop.shared.domain.clock import Clock
    from grooveloop.verification.domain.slice_verification import SliceVerification
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository


class VerificationRetry:
    def __init__(self, slice_verification_repository: SliceVerificationRepository, clock: Clock) -> None:
        self._slice_verification_repository = slice_verification_repository
        self._clock = clock

    def attempt(
        self,
        verification: SliceVerification,
        finished_at: datetime,
        max_retries: int,
        exhausted_cause: AgentRunCause,
        relaunch: Callable[[], AgentRun | None],
    ) -> None:
        policy = RetryPolicy(max_retries)
        if not policy.has_budget(verification.retries):
            verification.fail(exhausted_cause)
            self._slice_verification_repository.save(verification)

            return

        if not policy.is_due(verification.retries, finished_at, self._clock.now()):
            return

        run = relaunch()
        if run is None:
            return

        verification.retry_agent_run(run)

        self._slice_verification_repository.save(verification)

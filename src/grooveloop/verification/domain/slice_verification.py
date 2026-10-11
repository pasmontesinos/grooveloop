from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.verification.domain.exceptions import IllegalVerificationTransitionError
from grooveloop.verification.domain.verification_status import VerificationStatus

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.verification.domain.slice_id import SliceId
    from grooveloop.verification.domain.story_id import StoryId

_START_SOURCES = frozenset({VerificationStatus.EMPTY})
_CONCLUDE_SOURCES = frozenset({VerificationStatus.RUNNING})
_FAIL_SOURCES = frozenset({VerificationStatus.RUNNING})


class SliceVerification:
    def __init__(
        self,
        slice_id: SliceId,
        story_id: StoryId | None,
        status: VerificationStatus,
        agent_run_id: str | None = None,
        retries: int = 0,
        failure_cause: AgentRunCause = AgentRunCause.EMPTY,
    ) -> None:
        self._slice_id = slice_id
        self._story_id = story_id
        self._status = status
        self._agent_run_id = agent_run_id
        self._retries = retries
        self._failure_cause = failure_cause

    @property
    def slice_id(self) -> SliceId:
        return self._slice_id

    @property
    def story_id(self) -> StoryId | None:
        return self._story_id

    @property
    def status(self) -> VerificationStatus:
        return self._status

    @property
    def agent_run_id(self) -> str | None:
        return self._agent_run_id

    @property
    def retries(self) -> int:
        return self._retries

    @property
    def failure_cause(self) -> AgentRunCause:
        return self._failure_cause

    def record_agent_run(self, run: AgentRun) -> None:
        self._agent_run_id = run.run_id

    def retry_agent_run(self, run: AgentRun) -> None:
        self._agent_run_id = run.run_id
        self._retries += 1

    def is_pending(self) -> bool:
        return self._status is not VerificationStatus.CONCLUDED

    def is_running(self) -> bool:
        return self._status is VerificationStatus.RUNNING

    def can_start(self) -> bool:
        return self._status in _START_SOURCES

    def can_conclude(self) -> bool:
        return self._status in _CONCLUDE_SOURCES

    def start(self) -> None:
        self._transition(_START_SOURCES, VerificationStatus.RUNNING)

    def conclude(self) -> None:
        self._transition(_CONCLUDE_SOURCES, VerificationStatus.CONCLUDED)

    def fail(self, cause: AgentRunCause = AgentRunCause.EMPTY) -> None:
        self._transition(_FAIL_SOURCES, VerificationStatus.FAILED)
        self._failure_cause = cause

    def _transition(self, allowed: frozenset[VerificationStatus], target: VerificationStatus) -> None:
        if self._status not in allowed:
            raise IllegalVerificationTransitionError(
                f"Cannot move verification of slice {self._slice_id} from {self._status} to {target}"
            )

        self._status = target

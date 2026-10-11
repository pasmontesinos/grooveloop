from __future__ import annotations

from enum import StrEnum


class AgentOutcome(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    INTERRUPTED = "interrupted"
    FAILED = "failed"

    @property
    def is_failure(self) -> bool:
        return self in (AgentOutcome.INTERRUPTED, AgentOutcome.FAILED)

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_run_cause import AgentRunCause

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.shared.domain.agent_outcome import AgentOutcome


@dataclass(frozen=True)
class AgentRunVerdict:
    outcome: AgentOutcome
    cause: AgentRunCause = AgentRunCause.EMPTY
    finished_at: datetime | None = None

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.domain.agent_session import AgentSession
    from grooveloop.shared.domain.turn_growth import TurnGrowth


@dataclass(frozen=True)
class AgentSessionTranscript:
    session: AgentSession
    turn_growth: list[TurnGrowth] = field(default_factory=list)

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_log_action import AgentLogAction


@dataclass(frozen=True)
class AgentLogChunk:
    actions: list[AgentLogAction]
    offset: int

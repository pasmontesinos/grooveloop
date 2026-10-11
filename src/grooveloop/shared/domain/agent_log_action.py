from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentLogAction:
    description: str
    tool_use_id: str | None = None

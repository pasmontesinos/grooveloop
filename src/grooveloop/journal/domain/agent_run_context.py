from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AgentRunContext:
    repo: str
    story_id: str | None
    profile: str
    started_at: datetime

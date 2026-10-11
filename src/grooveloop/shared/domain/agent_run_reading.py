from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.cost_split import CostSplit
    from grooveloop.shared.domain.model_usage import ModelUsage
    from grooveloop.shared.domain.tool_tally import ToolTally


@dataclass(frozen=True)
class AgentRunReading:
    total_cost_usd: float | None = None
    models: list[ModelUsage] = field(default_factory=list)
    last_action: str | None = None
    turns: int | None = None
    subagents: int | None = None
    skills: list[str] = field(default_factory=list)
    tools: list[ToolTally] = field(default_factory=list)
    cost_split: CostSplit | None = None

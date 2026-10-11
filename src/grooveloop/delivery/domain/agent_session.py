from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_run_cause import AgentRunCause

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.delivery.domain.slice_id import SliceId
    from grooveloop.shared.domain.agent_outcome import AgentOutcome
    from grooveloop.shared.domain.agent_task_type import AgentTaskType
    from grooveloop.shared.domain.cost_split import CostSplit
    from grooveloop.shared.domain.model_usage import ModelUsage
    from grooveloop.shared.domain.tool_tally import ToolTally


@dataclass(frozen=True)
class AgentSession:
    slice_id: SliceId
    outcome: AgentOutcome
    task_type: AgentTaskType
    engine: str
    run_id: str
    started_at: datetime
    has_log: bool
    elapsed_seconds: float
    total_cost_usd: float | None = None
    models: list[ModelUsage] = field(default_factory=list)
    launch_model: str | None = None
    last_event_at: datetime | None = None
    last_action: str | None = None
    turns: int | None = None
    subagents: int | None = None
    skills: list[str] = field(default_factory=list)
    tools: list[ToolTally] = field(default_factory=list)
    cost_split: CostSplit | None = None
    profile: str | None = None
    cause: AgentRunCause = AgentRunCause.EMPTY

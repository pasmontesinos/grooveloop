from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_result import QueryResult

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class ModelUsageDTO:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class ToolTallyDTO:
    name: str
    count: int


@dataclass(frozen=True)
class CostShareDTO:
    token_class: str
    tokens: int
    cost_usd: float | None


@dataclass(frozen=True)
class CostSplitDTO:
    basis: str
    shares: list[CostShareDTO] = field(default_factory=list)


@dataclass(frozen=True)
class TurnGrowthDTO:
    turn: int
    added_tokens: int
    after_action: str | None = None


@dataclass(frozen=True)
class AgentSessionDTO:
    slice_number: str
    outcome: str
    task_type: str
    engine: str
    run_id: str
    started_at: datetime
    has_log: bool
    elapsed_seconds: float
    total_cost_usd: float | None
    models: list[ModelUsageDTO]
    launch_model: str | None = None
    last_event_at: datetime | None = None
    last_action: str | None = None
    turns: int | None = None
    subagents: int | None = None
    skills: list[str] = field(default_factory=list)
    tools: list[ToolTallyDTO] = field(default_factory=list)
    cost_split: CostSplitDTO | None = None
    turn_growth: list[TurnGrowthDTO] = field(default_factory=list)
    profile: str | None = None
    cause: str | None = None


@dataclass(frozen=True)
class ListRepoSessionsQueryResult(QueryResult):
    sessions: list[AgentSessionDTO]


@dataclass(frozen=True)
class ListRepoSessionsQuery(Query[ListRepoSessionsQueryResult]):
    repo: str

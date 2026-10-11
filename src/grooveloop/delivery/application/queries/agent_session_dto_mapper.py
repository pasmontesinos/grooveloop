from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.list_repo_sessions import (
    AgentSessionDTO,
    CostShareDTO,
    CostSplitDTO,
    ModelUsageDTO,
    ToolTallyDTO,
    TurnGrowthDTO,
)

if TYPE_CHECKING:
    from grooveloop.delivery.domain.agent_session import AgentSession
    from grooveloop.shared.domain.cost_split import CostSplit
    from grooveloop.shared.domain.model_usage import ModelUsage
    from grooveloop.shared.domain.turn_growth import TurnGrowth


def agent_session_dto_from_domain(
    session: AgentSession, turn_growth: list[TurnGrowth] | None = None
) -> AgentSessionDTO:
    return AgentSessionDTO(
        slice_number=session.slice_id.value,
        outcome=session.outcome.value,
        task_type=session.task_type.value,
        engine=session.engine,
        run_id=session.run_id,
        started_at=session.started_at,
        has_log=session.has_log,
        elapsed_seconds=session.elapsed_seconds,
        total_cost_usd=session.total_cost_usd,
        models=[_model_usage(model) for model in session.models],
        launch_model=session.launch_model,
        last_event_at=session.last_event_at,
        last_action=session.last_action,
        turns=session.turns,
        subagents=session.subagents,
        skills=list(session.skills),
        tools=[ToolTallyDTO(name=tool.name, count=tool.count) for tool in session.tools],
        cost_split=_cost_split(session.cost_split) if session.cost_split is not None else None,
        turn_growth=[
            TurnGrowthDTO(turn=growth.turn, added_tokens=growth.added_tokens, after_action=growth.after_action)
            for growth in turn_growth or []
        ],
        profile=session.profile,
        cause=session.cause.value,
    )


def _model_usage(model: ModelUsage) -> ModelUsageDTO:
    return ModelUsageDTO(
        model=model.model,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        cache_read_tokens=model.cache_read_tokens,
        cache_creation_tokens=model.cache_creation_tokens,
        cost_usd=model.cost_usd,
    )


def _cost_split(cost_split: CostSplit) -> CostSplitDTO:
    return CostSplitDTO(
        basis=cost_split.basis.value,
        shares=[
            CostShareDTO(token_class=share.token_class.value, tokens=share.tokens, cost_usd=share.cost_usd)
            for share in cost_split.shares
        ],
    )

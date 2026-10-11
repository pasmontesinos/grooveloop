from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.cli.watch_render import CostShareLine, ModelLine, SessionLine, ToolTallyLine
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.unstarted_run import is_unstarted

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.shared.application.queries.list_repo_sessions import AgentSessionDTO

_OUTCOME_LABELS = {
    AgentOutcome.RUNNING.value: "running",
    AgentOutcome.SUCCEEDED.value: "done",
    AgentOutcome.INTERRUPTED.value: "interrupted",
    AgentOutcome.FAILED.value: "failed",
}
_UNSTARTED_LABEL = "unstarted"


def session_line(session: AgentSessionDTO, now: datetime) -> SessionLine:
    return SessionLine(
        outcome=_outcome(session, now),
        task_type=session.task_type,
        engine=session.engine,
        elapsed_seconds=session.elapsed_seconds,
        run_id=session.run_id,
        profile=session.profile,
        total_cost_usd=session.total_cost_usd,
        models=[
            ModelLine(
                model.model,
                model.cost_usd,
                model.input_tokens,
                model.output_tokens,
                model.cache_read_tokens,
                model.cache_creation_tokens,
            )
            for model in session.models
        ],
        launch_model=session.launch_model,
        silent_seconds=_silent_seconds(session, now),
        last_action=session.last_action,
        turns=session.turns,
        subagents=session.subagents,
        skills=session.skills,
        tools=[ToolTallyLine(tool.name, tool.count) for tool in session.tools],
        cost_shares=_cost_shares(session),
        cause=session.cause,
    )


def _cost_shares(session: AgentSessionDTO) -> list[CostShareLine]:
    if session.cost_split is None:
        return []

    return [CostShareLine(share.token_class, share.tokens, share.cost_usd) for share in session.cost_split.shares]


def _outcome(session: AgentSessionDTO, now: datetime) -> str:
    if session.outcome == AgentOutcome.RUNNING.value and is_unstarted(session.has_log, session.started_at, now):
        return _UNSTARTED_LABEL

    return _OUTCOME_LABELS[session.outcome]


def _silent_seconds(session: AgentSessionDTO, now: datetime) -> float | None:
    if session.last_event_at is None:
        return None

    return max(0.0, (now - session.last_event_at).total_seconds())

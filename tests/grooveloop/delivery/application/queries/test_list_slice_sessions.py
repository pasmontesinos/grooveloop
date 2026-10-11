from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.delivery.application.queries.list_slice_sessions import (
    ListSliceSessionsQuery,
    ListSliceSessionsQueryHandler,
)
from grooveloop.delivery.domain.agent_session import AgentSession
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.queries.list_repo_sessions import CostShareDTO, CostSplitDTO, TurnGrowthDTO
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.cost_basis import CostBasis
from grooveloop.shared.domain.cost_share import CostShare
from grooveloop.shared.domain.cost_split import CostSplit
from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.domain.turn_growth import TurnGrowth
from tests.playground.shared.infrastructure.fake_agent_session_repository import (
    FakeAgentSessionRepository,
)


class TestListSliceSessionsQueryHandler:
    def test_returns_the_sessions_of_the_repo_and_slice_as_dtos(self) -> None:
        session = AgentSession(
            slice_id=SliceId("12"),
            outcome=AgentOutcome.SUCCEEDED,
            task_type=AgentTaskType.IMPLEMENT_SLICE,
            engine="claude",
            run_id="run-12",
            started_at=datetime(2026, 6, 30, 11, 58, 0, tzinfo=UTC),
            has_log=True,
            elapsed_seconds=83.0,
            total_cost_usd=0.42,
            models=[
                ModelUsage(
                    model="claude-opus-4",
                    input_tokens=10,
                    output_tokens=20,
                    cache_read_tokens=0,
                    cache_creation_tokens=0,
                    cost_usd=0.42,
                )
            ],
            launch_model="opus",
            last_event_at=datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC),
            profile="implementer",
        )
        repository = FakeAgentSessionRepository({("owner/repo", "12"): [session]})
        handler = ListSliceSessionsQueryHandler(agent_session_repository=repository)

        result = handler(ListSliceSessionsQuery(repo="owner/repo", slice_id="12"))

        assert len(result.sessions) == 1
        assert result.sessions[0].outcome == "succeeded"
        assert result.sessions[0].task_type == "implement_slice"
        assert result.sessions[0].engine == "claude"
        assert result.sessions[0].total_cost_usd == 0.42
        assert result.sessions[0].models[0].model == "claude-opus-4"
        assert result.sessions[0].launch_model == "opus"
        assert result.sessions[0].last_event_at == datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
        assert result.sessions[0].run_id == "run-12"
        assert result.sessions[0].profile == "implementer"
        assert result.sessions[0].started_at == datetime(2026, 6, 30, 11, 58, 0, tzinfo=UTC)
        assert result.sessions[0].has_log is True

    def test_returns_the_cost_split_of_the_session(self) -> None:
        split = CostSplit(
            basis=CostBasis.DERIVED,
            shares=[CostShare(TokenClass.INPUT, 10, 0.01)],
        )
        session = AgentSession(
            slice_id=SliceId("12"),
            outcome=AgentOutcome.SUCCEEDED,
            task_type=AgentTaskType.IMPLEMENT_SLICE,
            engine="claude",
            run_id="run-12",
            started_at=datetime(2026, 6, 30, 11, 58, 0, tzinfo=UTC),
            has_log=True,
            elapsed_seconds=1.0,
            cost_split=split,
        )
        repository = FakeAgentSessionRepository({("owner/repo", "12"): [session]})
        handler = ListSliceSessionsQueryHandler(agent_session_repository=repository)

        result = handler(ListSliceSessionsQuery(repo="owner/repo", slice_id="12"))

        assert result.sessions[0].cost_split == CostSplitDTO(
            basis="derived", shares=[CostShareDTO(token_class="input", tokens=10, cost_usd=0.01)]
        )

    def test_returns_empty_result_when_there_are_no_sessions(self) -> None:
        repository = FakeAgentSessionRepository({})
        handler = ListSliceSessionsQueryHandler(agent_session_repository=repository)

        result = handler(ListSliceSessionsQuery(repo="owner/repo", slice_id="12"))

        assert result.sessions == []


class TestListSliceSessionsQueryHandlerTurnGrowth:
    def test_returns_the_turn_growth_of_each_session_in_order(self) -> None:
        session = AgentSession(
            slice_id=SliceId("12"),
            outcome=AgentOutcome.SUCCEEDED,
            task_type=AgentTaskType.IMPLEMENT_SLICE,
            engine="claude",
            run_id="run-12",
            started_at=datetime(2026, 6, 30, 11, 58, 0, tzinfo=UTC),
            has_log=True,
            elapsed_seconds=1.0,
        )
        turns = [TurnGrowth(turn=2, added_tokens=6000, after_action="Bash · run tests")]
        repository = FakeAgentSessionRepository(
            {("owner/repo", "12"): [session]},
            turn_growth={("owner/repo", "12"): [turns]},
        )
        handler = ListSliceSessionsQueryHandler(agent_session_repository=repository)

        result = handler(ListSliceSessionsQuery(repo="owner/repo", slice_id="12"))

        assert result.sessions[0].turn_growth == [
            TurnGrowthDTO(turn=2, added_tokens=6000, after_action="Bash · run tests")
        ]

    def test_returns_no_turn_growth_when_the_repository_has_none(self) -> None:
        session = AgentSession(
            slice_id=SliceId("12"),
            outcome=AgentOutcome.SUCCEEDED,
            task_type=AgentTaskType.IMPLEMENT_SLICE,
            engine="claude",
            run_id="run-12",
            started_at=datetime(2026, 6, 30, 11, 58, 0, tzinfo=UTC),
            has_log=True,
            elapsed_seconds=1.0,
        )
        repository = FakeAgentSessionRepository({("owner/repo", "12"): [session]})
        handler = ListSliceSessionsQueryHandler(agent_session_repository=repository)

        result = handler(ListSliceSessionsQuery(repo="owner/repo", slice_id="12"))

        assert result.sessions[0].turn_growth == []

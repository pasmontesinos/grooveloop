from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.delivery.application.queries.list_repo_sessions import ListRepoSessionsQueryHandler
from grooveloop.delivery.domain.agent_session import AgentSession
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.queries.list_repo_sessions import ListRepoSessionsQuery
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from tests.playground.shared.infrastructure.fake_agent_session_repository import FakeAgentSessionRepository

_STARTED_AT = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


def _session(slice_id: str) -> AgentSession:
    return AgentSession(
        slice_id=SliceId(slice_id),
        outcome=AgentOutcome.RUNNING,
        task_type=AgentTaskType.IMPLEMENT_SLICE,
        engine="claude",
        run_id="run-1",
        started_at=_STARTED_AT,
        has_log=True,
        elapsed_seconds=12.0,
    )


class TestListRepoSessionsQueryHandler:
    def test_should_return_every_session_of_the_repo_with_its_slice(self) -> None:
        repository = FakeAgentSessionRepository(
            {("owner/repo", "11"): [_session("11")], ("owner/repo", "12"): [_session("12")]}
        )
        handler = ListRepoSessionsQueryHandler(agent_session_repository=repository)

        result = handler(ListRepoSessionsQuery(repo="owner/repo"))

        assert sorted(session.slice_number for session in result.sessions) == ["11", "12"]

    def test_should_return_no_session_for_a_repo_without_runs(self) -> None:
        handler = ListRepoSessionsQueryHandler(agent_session_repository=FakeAgentSessionRepository({}))

        assert handler(ListRepoSessionsQuery(repo="owner/repo")).sessions == []

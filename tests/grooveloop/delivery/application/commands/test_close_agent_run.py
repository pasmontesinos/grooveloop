from __future__ import annotations

from grooveloop.delivery.application.commands.close_agent_run import CloseAgentRunCommand, CloseAgentRunCommandHandler
from tests.playground.shared.infrastructure.fake_abandoned_agent_runs import FakeAbandonedAgentRuns


class TestCloseAgentRunCommandHandler:
    def test_closes_the_abandoned_run(self) -> None:
        abandoned_agent_runs = FakeAbandonedAgentRuns({"acme/sample": ["run-1"]})
        handler = CloseAgentRunCommandHandler(abandoned_agent_runs=abandoned_agent_runs)

        handler(CloseAgentRunCommand(run_id="run-1"))

        assert abandoned_agent_runs.closed == ["run-1"]
        assert abandoned_agent_runs.abandoned_run_ids("acme/sample") == []

from __future__ import annotations

from grooveloop.delivery.infrastructure.detectors.agent_run_abandoned_detector import AgentRunAbandonedDetector
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from tests.playground.shared.infrastructure.fake_abandoned_agent_runs import FakeAbandonedAgentRuns


class TestAgentRunAbandonedDetector:
    def test_emits_one_event_per_abandoned_run_of_the_target_repo(self) -> None:
        detector = AgentRunAbandonedDetector(
            abandoned_agent_runs=FakeAbandonedAgentRuns({"acme/sample": ["run-1", "run-2"], "acme/other": ["run-3"]}),
            target_repo=TargetRepo("acme/sample"),
        )

        events = list(detector.detect())

        assert [event.run_id for event in events] == ["run-1", "run-2"]

    def test_emits_nothing_when_no_run_is_abandoned(self) -> None:
        detector = AgentRunAbandonedDetector(
            abandoned_agent_runs=FakeAbandonedAgentRuns(), target_repo=TargetRepo("acme/sample")
        )

        assert list(detector.detect()) == []

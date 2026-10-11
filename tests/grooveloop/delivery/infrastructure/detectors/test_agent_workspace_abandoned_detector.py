from __future__ import annotations

from grooveloop.delivery.infrastructure.detectors.agent_workspace_abandoned_detector import (
    AgentWorkspaceAbandonedDetector,
)
from tests.playground.shared.infrastructure.fake_agent_workspaces import FakeAgentWorkspaces


class TestAgentWorkspaceAbandonedDetector:
    def test_emits_one_event_per_finished_run_that_keeps_its_workspace(self) -> None:
        detector = AgentWorkspaceAbandonedDetector(agent_workspaces=FakeAgentWorkspaces(["run-1", "run-2"]))

        events = list(detector.detect())

        assert [event.run_id for event in events] == ["run-1", "run-2"]

    def test_emits_nothing_when_no_run_keeps_a_workspace(self) -> None:
        detector = AgentWorkspaceAbandonedDetector(agent_workspaces=FakeAgentWorkspaces())

        assert list(detector.detect()) == []

    def test_caps_the_events_of_a_single_tick(self) -> None:
        run_ids = [f"run-{index:03d}" for index in range(50)]
        detector = AgentWorkspaceAbandonedDetector(agent_workspaces=FakeAgentWorkspaces(run_ids))

        events = list(detector.detect())

        assert len(events) == 20
        assert [event.run_id for event in events] == run_ids[:20]

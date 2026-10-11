from __future__ import annotations

from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.agent_run_failed_detector import (
    AgentRunFailedDetector,
)
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestAgentRunFailedDetector:
    def test_leaves_the_interrupted_implementation_to_its_recovery(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, agent_run_id="run-1")]}
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.INTERRUPTED)
        )

        events = list(detector.detect())

        assert events == []

    def test_leaves_the_interrupted_reviewer_to_its_recovery(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12", status=SliceStatus.UNDER_REVIEW, pull_request=pull_request, agent_run_id="run-1"
                    )
                ]
            }
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.INTERRUPTED)
        )

        events = list(detector.detect())

        assert events == []

    def test_emits_event_when_the_agent_failed_without_opening_a_pull_request(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, agent_run_id="run-1")]}
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_emits_event_when_the_reviewer_run_failed_under_review(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12", status=SliceStatus.UNDER_REVIEW, pull_request=pull_request, agent_run_id="run-1"
                    )
                ]
            }
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        events = list(detector.detect())

        assert [event.slice_id.value for event in events] == ["12"]

    def test_does_not_emit_while_the_reviewer_run_is_still_running(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12", status=SliceStatus.UNDER_REVIEW, pull_request=pull_request, agent_run_id="run-1"
                    )
                ]
            }
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.RUNNING)
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_while_the_agent_is_still_running(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, agent_run_id="run-1")]}
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.RUNNING)
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_when_the_slice_already_has_an_anchored_pull_request(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12", status=SliceStatus.DISPATCHED, pull_request=pull_request, agent_run_id="run-1"
                    )
                ]
            }
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_when_an_open_pull_request_is_linked_to_the_slice(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12", status=SliceStatus.DISPATCHED, pull_request=pull_request, agent_run_id="run-1"
                    )
                ]
            }
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_for_a_non_dispatched_slice(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.PR_OPEN, agent_run_id="run-1")]}
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        assert list(detector.detect()) == []

    def test_does_not_emit_when_the_slice_has_no_recorded_run(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED)]}
        )
        detector = AgentRunFailedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        assert list(detector.detect()) == []

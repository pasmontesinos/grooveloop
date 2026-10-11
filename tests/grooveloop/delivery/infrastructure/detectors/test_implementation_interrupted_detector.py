from __future__ import annotations

from grooveloop.delivery.domain.events import ImplementationInterrupted
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.implementation_interrupted_detector import (
    ImplementationInterruptedDetector,
)
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestImplementationInterruptedDetector:
    def test_emits_the_run_of_a_dispatched_slice_whose_implementation_was_interrupted(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, agent_run_id="run-1")]}
        )
        detector = ImplementationInterruptedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.INTERRUPTED)
        )

        events = list(detector.detect())

        assert events == [ImplementationInterrupted(slice_id=SliceId("12"), run_id="run-1")]

    def test_ignores_an_implementation_that_failed(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, agent_run_id="run-1")]}
        )
        detector = ImplementationInterruptedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.FAILED)
        )

        assert list(detector.detect()) == []

    def test_ignores_an_interrupted_run_once_the_slice_has_a_pull_request(self) -> None:
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
        detector = ImplementationInterruptedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.INTERRUPTED)
        )

        assert list(detector.detect()) == []

    def test_ignores_an_interrupted_reviewer(self) -> None:
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
        detector = ImplementationInterruptedDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.INTERRUPTED)
        )

        assert list(detector.detect()) == []

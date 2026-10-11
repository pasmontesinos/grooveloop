from __future__ import annotations

from grooveloop.delivery.domain.events import ImplementationIncomplete
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.detectors.implementation_incomplete_detector import (
    ImplementationIncompleteDetector,
)
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestImplementationIncompleteDetector:
    def test_emits_the_run_of_a_dispatched_slice_whose_implementation_succeeded_without_pull_request(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, agent_run_id="run-1")]}
        )
        detector = ImplementationIncompleteDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.SUCCEEDED)
        )

        events = list(detector.detect())

        assert events == [ImplementationIncomplete(slice_id=SliceId("12"), run_id="run-1")]

    def test_ignores_an_implementation_still_running(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [SliceMother.create(slice_id="12", status=SliceStatus.DISPATCHED, agent_run_id="run-1")]}
        )
        detector = ImplementationIncompleteDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.RUNNING)
        )

        assert list(detector.detect()) == []

    def test_ignores_a_succeeded_implementation_once_the_slice_has_a_pull_request(self) -> None:
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
        detector = ImplementationIncompleteDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.SUCCEEDED)
        )

        assert list(detector.detect()) == []

    def test_ignores_a_succeeded_reviewer(self) -> None:
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
        detector = ImplementationIncompleteDetector(
            slice_repository=repository, agent_runner=FakeAgentRunner(outcome=AgentOutcome.SUCCEEDED)
        )

        assert list(detector.detect()) == []

from __future__ import annotations

from grooveloop.delivery.application.commands.fail_addressing_changes import (
    FailAddressingChangesCommand,
    FailAddressingChangesCommandHandler,
)
from grooveloop.delivery.application.services.agent_run_failure_cause import AgentRunFailureCause
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository


class TestFailAddressingChangesCommandHandler:
    def test_fails_a_changes_requested_slice(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.CHANGES_REQUESTED)
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = FailAddressingChangesCommandHandler(
            slice_repository=repository, agent_run_failure_cause=AgentRunFailureCause(FakeAgentRunner())
        )

        handler(FailAddressingChangesCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.FAILED

    def test_fails_the_slice_with_the_cause_of_the_failed_run(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.CHANGES_REQUESTED, agent_run_id="run-12")
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        agent_runner = FakeAgentRunner(verdict=AgentRunVerdict(AgentOutcome.FAILED, AgentRunCause.AUTH))
        handler = FailAddressingChangesCommandHandler(
            slice_repository=repository, agent_run_failure_cause=AgentRunFailureCause(agent_runner)
        )

        handler(FailAddressingChangesCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.failure_cause.value == "auth"

    def test_is_idempotent_when_slice_is_not_changes_requested(self) -> None:
        a_slice = SliceMother.create(slice_id="12", status=SliceStatus.FAILED, agent_run_id="run-12")
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        handler = FailAddressingChangesCommandHandler(
            slice_repository=repository, agent_run_failure_cause=AgentRunFailureCause(FakeAgentRunner())
        )

        handler(FailAddressingChangesCommand(slice_id="12"))

        result = repository.find(SliceId("12"))
        assert result is not None
        assert result.status == SliceStatus.FAILED

    def test_does_nothing_when_slice_is_missing(self) -> None:
        repository = FakeSliceRepository({StoryId("10"): []})
        handler = FailAddressingChangesCommandHandler(
            slice_repository=repository, agent_run_failure_cause=AgentRunFailureCause(FakeAgentRunner())
        )

        handler(FailAddressingChangesCommand(slice_id="404"))

        assert repository.find(SliceId("404")) is None

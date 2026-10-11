from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import create_autospec

from grooveloop.delivery.application.commands.relaunch_implementation import (
    RelaunchImplementationCommand,
    RelaunchImplementationCommandHandler,
)
from grooveloop.delivery.application.services.implementation_recovery import ImplementationRecovery
from grooveloop.delivery.application.services.slice_retry import SliceRetry
from grooveloop.delivery.application.tasks.implementation_task import ImplementationTask
from grooveloop.delivery.application.tasks.story_journal_section import StoryJournalSection
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.application.queries.get_story_spec import GetStorySpecQuery, GetStorySpecQueryResult
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.clock import Clock
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.fake_agent_profiles import FakeAgentProfiles
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_query_bus import FakeQueryBus
from tests.playground.shared.infrastructure.fake_slice_repository import FakeSliceRepository

_FINISHED_AT = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)


def _clock(now: datetime) -> Any:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = now

    return clock


def _interrupted(cause: AgentRunCause = AgentRunCause.NETWORK) -> AgentRunVerdict:
    return AgentRunVerdict(AgentOutcome.INTERRUPTED, cause, finished_at=_FINISHED_AT)


def _handler(
    repository: FakeSliceRepository, agent_runner: FakeAgentRunner, now: datetime
) -> RelaunchImplementationCommandHandler:
    query_bus = FakeQueryBus({GetStorySpecQuery: lambda _query: GetStorySpecQueryResult(spec_text="the spec")})

    return RelaunchImplementationCommandHandler(
        slice_repository=repository,
        agent_runner=agent_runner,
        implementation_recovery=ImplementationRecovery(
            agent_runner=agent_runner,
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles(
                [
                    AgentProfile(
                        name="developer", engine="claude", model="opus", skills=[], context_files=[], persona="persona"
                    )
                ]
            ),
            implementation_task=ImplementationTask(query_bus, StoryJournalSection(query_bus)),
        ),
        slice_retry=SliceRetry(slice_repository=repository, clock=_clock(now)),
    )


def _command(max_retries: int = 2, run_id: str = "run-1") -> RelaunchImplementationCommand:
    return RelaunchImplementationCommand(
        slice_id="12", run_id=run_id, workdir="/tmp/wd", repo="owner/repo", max_retries=max_retries
    )


class TestRelaunchImplementationCommandHandler:
    def test_should_redispatch_the_implementation_once_the_wait_has_passed(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(minutes=2))

        handler(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.IMPLEMENT_SLICE
        assert agent_runner.last_slice_id == "12"
        assert 'Implement the slice "Second" of spec #10' in agent_runner.last_instruction
        assert a_slice.status == SliceStatus.DISPATCHED
        assert a_slice.retries == 1
        assert a_slice.agent_run_id == "fake-run"

    def test_should_not_redispatch_before_the_wait_has_passed(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(minutes=2) - timedelta(seconds=1))

        handler(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.dispatched_count == 0
        assert a_slice.retries == 0
        assert a_slice.agent_run_id == "run-1"

    def test_should_wait_four_times_longer_after_each_spent_retry(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                        retries=1,
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())

        _handler(repository, agent_runner, _FINISHED_AT + timedelta(minutes=8) - timedelta(seconds=1))(_command())
        dispatched_before_the_wait = agent_runner.dispatched_count
        _handler(repository, agent_runner, _FINISHED_AT + timedelta(minutes=8))(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert dispatched_before_the_wait == 0
        assert agent_runner.dispatched_count == 1
        assert a_slice.retries == 2

    def test_should_fail_the_slice_with_the_cause_when_the_retries_are_spent(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                        retries=2,
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted(AgentRunCause.OVERLOADED))
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command(max_retries=2))

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.dispatched_count == 0
        assert a_slice.status == SliceStatus.FAILED
        assert a_slice.failure_cause.value == "overloaded"

    def test_should_fail_the_slice_without_waiting_when_retries_are_disabled(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())
        handler = _handler(repository, agent_runner, _FINISHED_AT)

        handler(_command(max_retries=0))

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.dispatched_count == 0
        assert a_slice.status == SliceStatus.FAILED
        assert a_slice.failure_cause.value == "network"

    def test_should_redispatch_a_single_time_when_two_ticks_see_the_same_interrupted_run(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())
        handler(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.dispatched_count == 1
        assert a_slice.retries == 1

    def test_should_ignore_a_run_that_is_not_the_one_of_the_slice(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-2",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command(run_id="run-1"))

        assert agent_runner.dispatched_count == 0

    def test_should_ignore_a_slice_that_already_has_a_pull_request(self) -> None:
        pull_request = PullRequest(number=PullRequestNumber(42), comments=[])
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        pull_request=pull_request,
                        agent_run_id="run-1",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.dispatched_count == 0
        assert a_slice.status == SliceStatus.DISPATCHED

    def test_should_ignore_a_run_that_was_not_interrupted(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=AgentRunVerdict(AgentOutcome.RUNNING))
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.dispatched_count == 0
        assert a_slice.status == SliceStatus.DISPATCHED

    def test_should_point_the_redispatched_agent_to_the_branch_the_previous_attempt_pushed(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted(), pushed_branch="feat/previous-attempt")
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        assert "`feat/previous-attempt`" in agent_runner.last_instruction

    def test_should_not_mention_a_previous_branch_when_none_reached_origin(self) -> None:
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    SliceMother.create(
                        slice_id="12",
                        status=SliceStatus.DISPATCHED,
                        story_id="10",
                        title="Second",
                        description="the slice",
                        agent_run_id="run-1",
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        assert "Previous attempt" not in agent_runner.last_instruction

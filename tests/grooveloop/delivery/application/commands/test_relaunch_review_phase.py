from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

from grooveloop.delivery.application.commands.relaunch_review_phase import (
    RelaunchReviewPhaseCommand,
    RelaunchReviewPhaseCommandHandler,
)
from grooveloop.delivery.application.services.review_phase_recovery import ReviewPhaseRecovery
from grooveloop.delivery.application.services.slice_retry import SliceRetry
from grooveloop.delivery.application.tasks.addressing_task import AddressingTask
from grooveloop.delivery.application.tasks.review_task import ReviewTask
from grooveloop.delivery.application.tasks.story_journal_section import StoryJournalSection
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
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

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice import Slice

_FINISHED_AT = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)


def _clock(now: datetime) -> Any:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = now

    return clock


def _slice_with_a_pull_request_and_an_agent_run(
    status: SliceStatus, retries: int = 0, review_rounds: int = 1, agent_run_id: str = "run-1"
) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=status,
        story_id="10",
        title="Second",
        description="the slice",
        pull_request=PullRequest(number=PullRequestNumber(42), comments=[]),
        agent_run_id=agent_run_id,
        review_rounds=review_rounds,
        retries=retries,
    )


def _interrupted(cause: AgentRunCause = AgentRunCause.NETWORK) -> AgentRunVerdict:
    return AgentRunVerdict(AgentOutcome.INTERRUPTED, cause, finished_at=_FINISHED_AT)


def _handler(
    repository: FakeSliceRepository, agent_runner: FakeAgentRunner, now: datetime
) -> RelaunchReviewPhaseCommandHandler:
    return RelaunchReviewPhaseCommandHandler(
        slice_repository=repository,
        agent_runner=agent_runner,
        review_phase_recovery=ReviewPhaseRecovery(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles(
                [
                    AgentProfile(
                        name="developer", engine="claude", model="opus", skills=[], context_files=[], persona="persona"
                    ),
                    AgentProfile(
                        name="reviewer", engine="claude", model="opus", skills=[], context_files=[], persona="persona"
                    ),
                ]
            ),
            review_task=ReviewTask(StoryJournalSection(FakeQueryBus())),
            addressing_task=AddressingTask(),
        ),
        slice_retry=SliceRetry(slice_repository=repository, clock=_clock(now)),
    )


def _command(max_retries: int = 2, run_id: str = "run-1") -> RelaunchReviewPhaseCommand:
    return RelaunchReviewPhaseCommand(
        slice_id="12", run_id=run_id, workdir="/tmp/wd", repo="owner/repo", max_retries=max_retries
    )


def _redispatched(a_slice: Slice, now: datetime, max_retries: int = 2) -> tuple[Slice, FakeAgentRunner]:
    repository = FakeSliceRepository({StoryId("10"): [a_slice]})
    agent_runner = FakeAgentRunner(verdict=_interrupted())

    _handler(repository, agent_runner, now)(_command(max_retries=max_retries))

    found = repository.find(SliceId("12"))
    assert found is not None

    return found, agent_runner


class TestRelaunchReviewPhaseCommandHandler:
    def test_should_redispatch_the_interrupted_reviewer_keeping_the_slice_under_review(self) -> None:
        a_slice, agent_runner = _redispatched(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW), _FINISHED_AT + timedelta(minutes=2)
        )

        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        assert agent_runner.last_profile == "reviewer"
        assert 'Review the Pull Request #42 of the slice "Second"' in agent_runner.last_instruction
        assert a_slice.status == SliceStatus.UNDER_REVIEW
        assert a_slice.retries == 1
        assert a_slice.review_rounds == 1
        assert a_slice.agent_run_id == "fake-run"

    def test_should_redispatch_the_interrupted_correction_keeping_the_changes_requested(self) -> None:
        a_slice, agent_runner = _redispatched(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.CHANGES_REQUESTED),
            _FINISHED_AT + timedelta(minutes=2),
        )

        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.ADDRESS_REVIEW
        assert agent_runner.last_profile == "developer"
        assert "blocking verdict of the automatic reviewer" in agent_runner.last_instruction
        assert a_slice.status == SliceStatus.CHANGES_REQUESTED
        assert a_slice.retries == 1
        assert a_slice.review_rounds == 1
        assert a_slice.agent_run_id == "fake-run"

    def test_should_redispatch_the_correction_a_human_asked_for_as_a_human_review(self) -> None:
        _, agent_runner = _redispatched(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.CHANGES_REQUESTED, review_rounds=0),
            _FINISHED_AT + timedelta(minutes=2),
        )

        assert 'Address the "Request changes" review' in agent_runner.last_instruction

    def test_should_not_redispatch_before_the_wait_has_passed(self) -> None:
        a_slice, agent_runner = _redispatched(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW, retries=1),
            _FINISHED_AT + timedelta(minutes=8) - timedelta(seconds=1),
        )

        assert agent_runner.dispatched_count == 0
        assert a_slice.retries == 1
        assert a_slice.agent_run_id == "run-1"

    def test_should_fail_the_slice_with_the_cause_when_the_retries_are_spent(self) -> None:
        a_slice, agent_runner = _redispatched(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.CHANGES_REQUESTED, retries=2),
            _FINISHED_AT + timedelta(hours=1),
        )

        assert agent_runner.dispatched_count == 0
        assert a_slice.status == SliceStatus.FAILED
        assert a_slice.failure_cause.value == "network"

    def test_should_fail_the_slice_without_waiting_when_retries_are_disabled(self) -> None:
        a_slice, agent_runner = _redispatched(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW), _FINISHED_AT, max_retries=0
        )

        assert agent_runner.dispatched_count == 0
        assert a_slice.status == SliceStatus.FAILED

    def test_should_redispatch_a_single_time_when_two_ticks_see_the_same_interrupted_run(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW)]}
        )
        agent_runner = FakeAgentRunner(verdict=_interrupted())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())
        handler(_command())

        assert agent_runner.dispatched_count == 1

    def test_should_ignore_a_run_that_is_not_the_one_of_the_slice(self) -> None:
        _, agent_runner = _redispatched(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW, agent_run_id="run-2"),
            _FINISHED_AT + timedelta(hours=1),
        )

        assert agent_runner.dispatched_count == 0

    def test_should_ignore_a_slice_outside_the_review_phases(self) -> None:
        a_slice, agent_runner = _redispatched(
            _slice_with_a_pull_request_and_an_agent_run(SliceStatus.PR_OPEN), _FINISHED_AT + timedelta(hours=1)
        )

        assert agent_runner.dispatched_count == 0
        assert a_slice.status == SliceStatus.PR_OPEN

    def test_should_ignore_a_run_that_was_not_interrupted(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW)]}
        )
        agent_runner = FakeAgentRunner(verdict=AgentRunVerdict(AgentOutcome.RUNNING))

        _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))(_command())

        assert agent_runner.dispatched_count == 0

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

from grooveloop.delivery.application.commands.resume_review_phase import (
    ResumeReviewPhaseCommand,
    ResumeReviewPhaseCommandHandler,
)
from grooveloop.delivery.application.services.review_phase_recovery import ReviewPhaseRecovery
from grooveloop.delivery.application.services.slice_retry import SliceRetry
from grooveloop.delivery.application.tasks.addressing_task import AddressingTask
from grooveloop.delivery.application.tasks.review_task import ReviewTask
from grooveloop.delivery.application.tasks.story_journal_section import StoryJournalSection
from grooveloop.delivery.domain.pull_request import PullRequest
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_profile import AgentProfile
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
    status: SliceStatus,
    retries: int = 0,
    review_rounds: int = 1,
    review_verdict: ReviewVerdict = ReviewVerdict.EMPTY,
    pull_request: PullRequest | None = None,
) -> Slice:
    return SliceMother.create(
        slice_id="12",
        status=status,
        story_id="10",
        title="Second",
        description="the slice",
        pull_request=pull_request or PullRequest(number=PullRequestNumber(42), comments=[]),
        agent_run_id="run-1",
        review_verdict=review_verdict,
        review_rounds=review_rounds,
        retries=retries,
    )


def _succeeded() -> AgentRunVerdict:
    return AgentRunVerdict(AgentOutcome.SUCCEEDED, finished_at=_FINISHED_AT)


def _handler(
    repository: FakeSliceRepository, agent_runner: FakeAgentRunner, now: datetime
) -> ResumeReviewPhaseCommandHandler:
    return ResumeReviewPhaseCommandHandler(
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


def _command(max_retries: int = 2) -> ResumeReviewPhaseCommand:
    return ResumeReviewPhaseCommand(
        slice_id="12", run_id="run-1", workdir="/tmp/wd", repo="owner/repo", max_retries=max_retries
    )


class TestResumeReviewPhaseCommandHandler:
    def test_should_resume_the_reviewer_that_finished_without_a_verdict(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW)]}
        )
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(minutes=2))

        handler(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.resumed_count == 1
        assert agent_runner.last_resumed_run_id == "run-1"
        assert "`gh issue edit 12 --add-label review:<verdict>`" in agent_runner.last_resume_instruction
        assert "<!-- grooveloop:review -->" in agent_runner.last_resume_instruction
        assert a_slice.status == SliceStatus.UNDER_REVIEW
        assert a_slice.retries == 1
        assert a_slice.review_rounds == 1
        assert a_slice.agent_run_id == "resumed-run"

    def test_should_resume_the_correction_that_finished_without_new_commits(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.CHANGES_REQUESTED)]}
        )
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.resumed_count == 1
        assert "push to the PR branch" in agent_runner.last_resume_instruction
        assert a_slice.status == SliceStatus.CHANGES_REQUESTED
        assert a_slice.retries == 1
        assert a_slice.agent_run_id == "resumed-run"

    def test_should_redispatch_the_reviewer_when_its_run_cannot_be_resumed(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW)]}
        )
        agent_runner = FakeAgentRunner(verdict=_succeeded())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.REVIEW_SLICE
        assert a_slice.retries == 1
        assert a_slice.agent_run_id == "fake-run"

    def test_should_not_resume_a_reviewer_that_already_declared_its_verdict(self) -> None:
        a_slice = _slice_with_a_pull_request_and_an_agent_run(
            SliceStatus.UNDER_REVIEW, review_verdict=ReviewVerdict.BLOCKING
        )
        repository = FakeSliceRepository({StoryId("10"): [a_slice]})
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        assert agent_runner.resumed_count == 0

    def test_should_not_resume_a_correction_that_pushed_commits_after_the_review(self) -> None:
        pull_request = PullRequest(
            number=PullRequestNumber(42),
            comments=[],
            review_summary_at=_FINISHED_AT - timedelta(hours=2),
            last_commit_at=_FINISHED_AT - timedelta(hours=1),
        )
        repository = FakeSliceRepository(
            {
                StoryId("10"): [
                    _slice_with_a_pull_request_and_an_agent_run(
                        SliceStatus.CHANGES_REQUESTED, pull_request=pull_request
                    )
                ]
            }
        )
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        assert agent_runner.resumed_count == 0

    def test_should_not_resume_before_the_wait_has_passed(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW)]}
        )
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(minutes=2) - timedelta(seconds=1))

        handler(_command())

        assert agent_runner.resumed_count == 0

    def test_should_fail_the_slice_as_incomplete_when_the_retries_are_spent(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.CHANGES_REQUESTED, retries=2)]}
        )
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command(max_retries=2))

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.resumed_count == 0
        assert a_slice.status == SliceStatus.FAILED
        assert a_slice.failure_cause.value == "incomplete"

    def test_should_leave_the_slice_as_it_was_when_retries_are_disabled(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW)]}
        )
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command(max_retries=0))

        a_slice = repository.find(SliceId("12"))
        assert a_slice is not None
        assert agent_runner.resumed_count == 0
        assert a_slice.status == SliceStatus.UNDER_REVIEW
        assert a_slice.agent_run_id == "run-1"

    def test_should_resume_a_single_time_when_two_ticks_see_the_same_run(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW)]}
        )
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())
        handler(_command())

        assert agent_runner.resumed_count == 1

    def test_should_ignore_a_run_that_did_not_succeed(self) -> None:
        repository = FakeSliceRepository(
            {StoryId("10"): [_slice_with_a_pull_request_and_an_agent_run(SliceStatus.UNDER_REVIEW)]}
        )
        agent_runner = FakeAgentRunner(verdict=AgentRunVerdict(AgentOutcome.RUNNING), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        assert agent_runner.resumed_count == 0

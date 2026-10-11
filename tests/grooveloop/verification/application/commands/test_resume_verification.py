from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import create_autospec

from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.clock import Clock
from grooveloop.verification.application.commands.resume_verification import (
    ResumeVerificationCommand,
    ResumeVerificationCommandHandler,
)
from grooveloop.verification.application.services.verification_recovery import VerificationRecovery
from grooveloop.verification.application.services.verification_retry import VerificationRetry
from grooveloop.verification.application.tasks.verification_task import VerificationTask
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus
from tests.playground.shared.infrastructure.fake_agent_profiles import FakeAgentProfiles
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_slice_verification_repository import (
    FakeSliceVerificationRepository,
)

_FINISHED_AT = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)


def _clock(now: datetime) -> Any:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = now

    return clock


def _repository_with_a_running_verification(
    retries: int = 0, status: VerificationStatus = VerificationStatus.RUNNING
) -> FakeSliceVerificationRepository:
    return FakeSliceVerificationRepository(
        [SliceVerification(SliceId("11"), StoryId("10"), status, agent_run_id="run-1", retries=retries)]
    )


def _succeeded() -> AgentRunVerdict:
    return AgentRunVerdict(AgentOutcome.SUCCEEDED, finished_at=_FINISHED_AT)


def _handler(
    repository: FakeSliceVerificationRepository, agent_runner: FakeAgentRunner, now: datetime
) -> ResumeVerificationCommandHandler:
    return ResumeVerificationCommandHandler(
        slice_verification_repository=repository,
        agent_runner=agent_runner,
        verification_recovery=VerificationRecovery(
            agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
            agent_profiles=FakeAgentProfiles(
                [
                    AgentProfile(
                        name="verifier", engine="claude", model="sonnet", skills=[], context_files=[], persona="persona"
                    )
                ]
            ),
            verification_task=VerificationTask(),
        ),
        verification_retry=VerificationRetry(slice_verification_repository=repository, clock=_clock(now)),
    )


def _command(max_retries: int = 2) -> ResumeVerificationCommand:
    return ResumeVerificationCommand(
        slice_id="11",
        run_id="run-1",
        pull_request_number=42,
        title="Mark verify-deploy when creating the sub-issues",
        description="- **Observable verification:**\n\n  1. `gh pr view 42`.\n",
        workdir="/tmp/wd",
        repo="owner/repo",
        max_retries=max_retries,
    )


def _verification(repository: FakeSliceVerificationRepository) -> SliceVerification:
    verification = repository.find(SliceId("11"))
    assert verification is not None

    return verification


class TestResumeVerificationCommandHandler:
    def test_should_resume_the_verifier_that_finished_without_its_report(self) -> None:
        repository = _repository_with_a_running_verification()
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(minutes=2))

        handler(_command())

        verification = _verification(repository)
        assert agent_runner.resumed_count == 1
        assert agent_runner.last_resumed_run_id == "run-1"
        assert "`gh pr comment 42`" in agent_runner.last_resume_instruction
        assert "<!-- grooveloop:verify-deploy -->" in agent_runner.last_resume_instruction
        assert verification.status is VerificationStatus.RUNNING
        assert verification.retries == 1
        assert verification.agent_run_id == "resumed-run"

    def test_should_redispatch_the_verifier_when_its_run_cannot_be_resumed(self) -> None:
        repository = _repository_with_a_running_verification()
        agent_runner = FakeAgentRunner(verdict=_succeeded())
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        verification = _verification(repository)
        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.VERIFY_DEPLOY
        assert verification.retries == 1
        assert verification.agent_run_id == "fake-run"

    def test_should_not_resume_before_the_wait_has_passed(self) -> None:
        repository = _repository_with_a_running_verification(retries=1)
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(minutes=8) - timedelta(seconds=1))

        handler(_command())

        assert agent_runner.resumed_count == 0
        assert _verification(repository).agent_run_id == "run-1"

    def test_should_fail_the_verification_as_incomplete_when_the_retries_are_spent(self) -> None:
        repository = _repository_with_a_running_verification(retries=2)
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command(max_retries=2))

        verification = _verification(repository)
        assert agent_runner.resumed_count == 0
        assert verification.status is VerificationStatus.FAILED
        assert verification.failure_cause.value == "incomplete"

    def test_should_leave_the_verification_running_when_retries_are_disabled(self) -> None:
        repository = _repository_with_a_running_verification()
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command(max_retries=0))

        verification = _verification(repository)
        assert agent_runner.resumed_count == 0
        assert verification.status is VerificationStatus.RUNNING
        assert verification.agent_run_id == "run-1"

    def test_should_resume_a_single_time_when_two_ticks_see_the_same_run(self) -> None:
        repository = _repository_with_a_running_verification()
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())
        handler(_command())

        assert agent_runner.resumed_count == 1

    def test_should_ignore_a_verification_that_already_concluded(self) -> None:
        repository = _repository_with_a_running_verification(status=VerificationStatus.CONCLUDED)
        agent_runner = FakeAgentRunner(verdict=_succeeded(), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        assert agent_runner.resumed_count == 0

    def test_should_ignore_a_run_that_did_not_succeed(self) -> None:
        repository = _repository_with_a_running_verification()
        agent_runner = FakeAgentRunner(verdict=AgentRunVerdict(AgentOutcome.RUNNING), resumable=True)
        handler = _handler(repository, agent_runner, _FINISHED_AT + timedelta(hours=1))

        handler(_command())

        assert agent_runner.resumed_count == 0

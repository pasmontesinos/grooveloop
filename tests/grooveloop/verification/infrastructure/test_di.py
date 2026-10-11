from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec

from github import Github

from grooveloop.bootstrap import container
from grooveloop.shared.application.events.event_dispatcher import EventDispatcher
from grooveloop.shared.application.queries.pending_verifications import (
    PendingVerificationsQuery,
    PendingVerificationsQueryResult,
)
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.domain.agent_runner import AgentRunner
from grooveloop.shared.domain.agent_runner_registry import AgentRunnerRegistry
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.verification.domain.events import SliceReadyToVerify, VerificationConcluded, VerificationRunFailed
from grooveloop.verification.domain.merged_slice_signal import MergedSliceSignal
from grooveloop.verification.domain.pull_request_number import PullRequestNumber
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.domain.slice_verification import SliceVerification
from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository
from grooveloop.verification.domain.story_id import StoryId
from grooveloop.verification.domain.verification_status import VerificationStatus
from grooveloop.verification.infrastructure.github_merged_slice_signal import GithubMergedSliceSignal
from grooveloop.verification.infrastructure.github_slice_verification_repository import (
    GithubSliceVerificationRepository,
)
from tests.playground.shared.infrastructure.fake_agent_runner import FakeAgentRunner
from tests.playground.shared.infrastructure.fake_agent_runner_registry import FakeAgentRunnerRegistry
from tests.playground.shared.infrastructure.fake_slice_verification_repository import (
    FakeSliceVerificationRepository,
)
from tests.playground.shared.infrastructure.github_client import github_client_for_any_repo


def _repository(status: VerificationStatus) -> FakeSliceVerificationRepository:
    return FakeSliceVerificationRepository([SliceVerification(SliceId("11"), StoryId("10"), status)])


class TestVerificationModule:
    def test_should_build_its_github_adapters_for_the_target_repo(self) -> None:
        github = github_client_for_any_repo()
        with container.override(TargetRepo, TargetRepo("owner/repo")), container.override(Github, github):
            slice_verification_repository = container.get(SliceVerificationRepository)
            merged_slice_signal = container.get(MergedSliceSignal)

        assert isinstance(slice_verification_repository, GithubSliceVerificationRepository)
        assert isinstance(merged_slice_signal, GithubMergedSliceSignal)
        github.get_repo.assert_called_once_with("owner/repo")

    def test_should_answer_the_pending_verifications_query_through_the_query_bus(self) -> None:
        repository = _repository(VerificationStatus.RUNNING)

        with container.override(SliceVerificationRepository, repository):
            result: PendingVerificationsQueryResult | None = container.get(QueryBus).ask(
                PendingVerificationsQuery(story_id="10")
            )

        assert result is not None
        assert result.slice_ids == ["11"]

    def test_should_dispatch_the_verifier_when_a_slice_is_ready_to_verify(self) -> None:
        repository = _repository(VerificationStatus.EMPTY)
        agent_runner = FakeAgentRunner()

        with (
            container.override(SliceVerificationRepository, repository),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
        ):
            container.get(EventDispatcher).dispatch(
                SliceReadyToVerify(
                    slice_id=SliceId("11"),
                    pull_request_number=PullRequestNumber(42),
                    title="Mark verify-deploy when creating the sub-issues",
                    description="- **Observable verification:**\n\n  1. `gh pr view 42`.\n",
                )
            )

        assert agent_runner.dispatched_count == 1
        verification = repository.find(SliceId("11"))
        assert verification is not None
        assert verification.status == VerificationStatus.RUNNING

    def test_should_conclude_the_verification_when_the_report_marker_appears(self) -> None:
        repository = _repository(VerificationStatus.RUNNING)

        with container.override(SliceVerificationRepository, repository):
            container.get(EventDispatcher).dispatch(VerificationConcluded(slice_id=SliceId("11")))

        verification = repository.find(SliceId("11"))
        assert verification is not None
        assert verification.status == VerificationStatus.CONCLUDED

    def test_should_redispatch_the_verifier_when_its_run_was_interrupted(self) -> None:
        finished_at = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
        repository = FakeSliceVerificationRepository(
            [SliceVerification(SliceId("11"), StoryId("10"), VerificationStatus.RUNNING, agent_run_id="run-1")]
        )
        agent_runner = FakeAgentRunner(
            verdict=AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.NETWORK, finished_at=finished_at)
        )
        clock = create_autospec(Clock, spec_set=True, instance=True)
        clock.now.return_value = finished_at + timedelta(minutes=2)

        with (
            container.override(SliceVerificationRepository, repository),
            container.override(AgentRunner, agent_runner),
            container.override(AgentRunnerRegistry, FakeAgentRunnerRegistry(agent_runner)),
            container.override(Clock, clock),
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
            container.override(MaxRetries, MaxRetries(2)),
        ):
            container.get(EventDispatcher).dispatch(
                VerificationRunFailed(
                    slice_id=SliceId("11"),
                    run_id="run-1",
                    pull_request_number=PullRequestNumber(42),
                    title="Mark verify-deploy when creating the sub-issues",
                    description="- **Observable verification:**\n\n  1. `gh pr view 42`.\n",
                )
            )

        assert agent_runner.dispatched_count == 1
        verification = repository.find(SliceId("11"))
        assert verification is not None
        assert verification.retries == 1

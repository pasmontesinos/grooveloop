from __future__ import annotations

from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.verification.application.commands.verify_deployment import (
    VerifyDeploymentCommand,
    VerifyDeploymentCommandHandler,
)
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


def _verifier(model: str = "sonnet", engine: str = "claude") -> AgentProfile:
    return AgentProfile(
        name="verifier",
        engine=engine,
        model=model,
        skills=["verify-deploy"],
        context_files=[],
        persona="you are the deployment verifier",
    )


_DESCRIPTION_WITH_SECTION = """- **Type:** vertical
- **Observable verification:**

  1. `gh issue view 11 --json labels` -> includes `verify-deploy`.
"""


def _command(description: str = _DESCRIPTION_WITH_SECTION) -> VerifyDeploymentCommand:
    return VerifyDeploymentCommand(
        slice_id="11",
        pull_request_number=42,
        title="Mark verify-deploy when creating the sub-issues",
        description=description,
        workdir="/tmp/wd",
        repo="owner/repo",
    )


def _repository_with_a_not_started_verification() -> FakeSliceVerificationRepository:
    return FakeSliceVerificationRepository([SliceVerification(SliceId("11"), StoryId("10"), VerificationStatus.EMPTY)])


def _handler(
    repository: FakeSliceVerificationRepository, agent_runner: FakeAgentRunner
) -> VerifyDeploymentCommandHandler:
    return VerifyDeploymentCommandHandler(
        slice_verification_repository=repository,
        agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
        agent_profiles=FakeAgentProfiles([_verifier()]),
        verification_task=VerificationTask(),
    )


def _handler_without_profile(
    repository: FakeSliceVerificationRepository, agent_runner: FakeAgentRunner
) -> VerifyDeploymentCommandHandler:
    return VerifyDeploymentCommandHandler(
        slice_verification_repository=repository,
        agent_runner_registry=FakeAgentRunnerRegistry(agent_runner),
        agent_profiles=FakeAgentProfiles(),
        verification_task=VerificationTask(),
    )


class TestVerifyDeploymentCommandHandler:
    def test_dispatches_the_verifier_with_the_verify_deploy_task_type(self) -> None:
        agent_runner = FakeAgentRunner()

        _handler(_repository_with_a_not_started_verification(), agent_runner)(_command())

        assert agent_runner.dispatched_count == 1
        assert agent_runner.last_task_type == AgentTaskType.VERIFY_DEPLOY
        assert agent_runner.last_slice_id == "11"
        assert agent_runner.last_repo == "owner/repo"
        assert agent_runner.last_workdir == "/tmp/wd"
        assert agent_runner.last_model == "sonnet"

    def test_instructs_the_agent_to_wait_for_the_deployment_and_leave_one_report(self) -> None:
        agent_runner = FakeAgentRunner()

        _handler(_repository_with_a_not_started_verification(), agent_runner)(_command())

        instruction = agent_runner.last_instruction
        assert "you are the deployment verifier" in instruction
        assert "#42" in instruction
        assert "Mark verify-deploy when creating the sub-issues" in instruction
        assert "autonomous mode" in instruction
        assert "EXACTLY ONE comment" in instruction
        assert "<!-- grooveloop:verify-deploy -->" in instruction

    def test_forbids_delegating_the_wait_to_a_background_monitor(self) -> None:
        agent_runner = FakeAgentRunner()

        _handler(_repository_with_a_not_started_verification(), agent_runner)(_command())

        instruction = agent_runner.last_instruction
        assert "within this same turn" in instruction
        assert "do not set up background monitors" in instruction
        assert "the process dies" in instruction

    def test_asks_to_wait_in_the_foreground_for_long_commands(self) -> None:
        agent_runner = FakeAgentRunner()

        _handler(_repository_with_a_not_started_verification(), agent_runner)(_command())

        assert "wait in the foreground" in agent_runner.last_instruction

    def test_asks_for_a_separate_verdict_for_the_deployment_and_for_the_increment(self) -> None:
        agent_runner = FakeAgentRunner()

        _handler(_repository_with_a_not_started_verification(), agent_runner)(_command())

        instruction = agent_runner.last_instruction
        assert "Deploy verdict" in instruction
        assert "Increment verdict" in instruction

    def test_quotes_the_verification_section_of_the_slice_issue(self) -> None:
        agent_runner = FakeAgentRunner()

        _handler(_repository_with_a_not_started_verification(), agent_runner)(_command())

        instruction = agent_runner.last_instruction
        assert "gh issue view 11 --json labels" in instruction
        assert "no verification section" not in instruction

    def test_orders_to_resolve_the_placeholders_of_the_section(self) -> None:
        agent_runner = FakeAgentRunner()

        _handler(_repository_with_a_not_started_verification(), agent_runner)(_command())

        instruction = agent_runner.last_instruction
        assert "unresolved placeholders" in instruction
        assert "`owner/repo`" in instruction

    def test_declares_the_missing_section_instead_of_inventing_it(self) -> None:
        agent_runner = FakeAgentRunner()
        command = _command(description="- **Type:** vertical\n- **Depends on:** none.\n")

        _handler(_repository_with_a_not_started_verification(), agent_runner)(command)

        instruction = agent_runner.last_instruction
        assert "no verification section in the sub-issue" in instruction
        assert "Do not make it up" in instruction
        assert "does not degrade the service" in instruction

    def test_starts_the_verification(self) -> None:
        repository = _repository_with_a_not_started_verification()

        _handler(repository, FakeAgentRunner())(_command())

        verification = repository.find(SliceId("11"))
        assert verification is not None
        assert verification.status == VerificationStatus.RUNNING

    def test_does_nothing_when_the_verification_already_started(self) -> None:
        agent_runner = FakeAgentRunner()
        repository = FakeSliceVerificationRepository(
            [SliceVerification(SliceId("11"), StoryId("10"), VerificationStatus.RUNNING)]
        )

        _handler(repository, agent_runner)(_command())

        assert agent_runner.dispatched_count == 0

    def test_does_nothing_when_the_slice_is_not_marked_for_verification(self) -> None:
        agent_runner = FakeAgentRunner()

        _handler(FakeSliceVerificationRepository([]), agent_runner)(_command())

        assert agent_runner.dispatched_count == 0

    def test_records_the_agent_run_of_the_verifier(self) -> None:
        repository = _repository_with_a_not_started_verification()

        _handler(repository, FakeAgentRunner())(_command())

        verification = repository.find(SliceId("11"))
        assert verification is not None
        assert verification.agent_run_id == "fake-run"

    def test_does_nothing_when_the_verifier_profile_is_missing(self) -> None:
        agent_runner = FakeAgentRunner()
        repository = _repository_with_a_not_started_verification()

        _handler_without_profile(repository, agent_runner)(_command())

        assert agent_runner.dispatched_count == 0
        verification = repository.find(SliceId("11"))
        assert verification is not None
        assert verification.status == VerificationStatus.EMPTY

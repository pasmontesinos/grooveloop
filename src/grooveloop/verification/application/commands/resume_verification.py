from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.verification.domain.slice_id import SliceId

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.shared.domain.agent_runner import AgentRunner
    from grooveloop.verification.application.services.verification_recovery import VerificationRecovery
    from grooveloop.verification.application.services.verification_retry import VerificationRetry
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository


@dataclass(frozen=True)
class ResumeVerificationCommand(Command):
    slice_id: str
    run_id: str
    pull_request_number: int
    title: str
    description: str
    workdir: str
    repo: str
    max_retries: int = 0


class ResumeVerificationCommandHandler(CommandHandler[ResumeVerificationCommand, None]):
    def __init__(
        self,
        slice_verification_repository: SliceVerificationRepository,
        agent_runner: AgentRunner,
        verification_recovery: VerificationRecovery,
        verification_retry: VerificationRetry,
    ) -> None:
        self._slice_verification_repository = slice_verification_repository
        self._agent_runner = agent_runner
        self._recovery = verification_recovery
        self._retry = verification_retry

    def __call__(self, command: ResumeVerificationCommand) -> None:
        if command.max_retries == 0:
            return

        verification = self._slice_verification_repository.find(SliceId(command.slice_id))
        if verification is None or not self._recovery.awaits_recovery(verification, command.run_id):
            return

        verdict = self._agent_runner.verdict_of(command.run_id)
        if verdict.outcome is not AgentOutcome.SUCCEEDED or verdict.finished_at is None:
            return

        self._retry.attempt(
            verification,
            verdict.finished_at,
            command.max_retries,
            AgentRunCause.INCOMPLETE,
            lambda: self._resume(command),
        )

    def _resume(self, command: ResumeVerificationCommand) -> AgentRun | None:
        resumed = self._agent_runner.resume(command.run_id, self._recovery.resumption(command.pull_request_number))
        if resumed is not None:
            return resumed

        return self._recovery.redispatch(
            command.slice_id,
            command.pull_request_number,
            command.title,
            command.description,
            command.workdir,
            command.repo,
        )

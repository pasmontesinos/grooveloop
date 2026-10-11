from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.verification.domain.slice_id import SliceId

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_runner import AgentRunner
    from grooveloop.verification.application.services.verification_recovery import VerificationRecovery
    from grooveloop.verification.application.services.verification_retry import VerificationRetry
    from grooveloop.verification.domain.slice_verification_repository import SliceVerificationRepository


@dataclass(frozen=True)
class RecoverVerificationCommand(Command):
    slice_id: str
    run_id: str
    pull_request_number: int
    title: str
    description: str
    workdir: str
    repo: str
    max_retries: int = 0


class RecoverVerificationCommandHandler(CommandHandler[RecoverVerificationCommand, None]):
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

    def __call__(self, command: RecoverVerificationCommand) -> None:
        verification = self._slice_verification_repository.find(SliceId(command.slice_id))
        if verification is None or not self._recovery.awaits_recovery(verification, command.run_id):
            return

        verdict = self._agent_runner.verdict_of(command.run_id)
        if not verdict.outcome.is_failure or verdict.finished_at is None:
            return

        if verdict.outcome is AgentOutcome.FAILED:
            verification.fail(verdict.cause)
            self._slice_verification_repository.save(verification)

            return

        self._retry.attempt(
            verification,
            verdict.finished_at,
            command.max_retries,
            verdict.cause,
            lambda: self._recovery.redispatch(
                command.slice_id,
                command.pull_request_number,
                command.title,
                command.description,
                command.workdir,
                command.repo,
            ),
        )

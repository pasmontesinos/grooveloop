from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause

if TYPE_CHECKING:
    from grooveloop.delivery.application.services.implementation_recovery import ImplementationRecovery
    from grooveloop.delivery.application.services.slice_retry import SliceRetry
    from grooveloop.delivery.domain.slice import Slice
    from grooveloop.delivery.domain.slice_repository import SliceRepository
    from grooveloop.shared.domain.agent_run import AgentRun
    from grooveloop.shared.domain.agent_runner import AgentRunner


@dataclass(frozen=True)
class ResumeImplementationCommand(Command):
    slice_id: str
    run_id: str
    workdir: str
    repo: str
    max_retries: int = 0
    journal_enabled: bool = False


class ResumeImplementationCommandHandler(CommandHandler[ResumeImplementationCommand, None]):
    def __init__(
        self,
        slice_repository: SliceRepository,
        agent_runner: AgentRunner,
        implementation_recovery: ImplementationRecovery,
        slice_retry: SliceRetry,
    ) -> None:
        self._slice_repository = slice_repository
        self._agent_runner = agent_runner
        self._recovery = implementation_recovery
        self._retry = slice_retry

    def __call__(self, command: ResumeImplementationCommand) -> None:
        if command.max_retries == 0:
            return

        a_slice = self._slice_repository.find(SliceId(command.slice_id))
        if a_slice is None or not self._recovery.awaits_recovery(a_slice, command.run_id):
            return

        verdict = self._agent_runner.verdict_of(command.run_id)
        if verdict.outcome is not AgentOutcome.SUCCEEDED or verdict.finished_at is None:
            return

        self._retry.attempt(
            a_slice,
            verdict.finished_at,
            command.max_retries,
            AgentRunCause.INCOMPLETE,
            lambda: self._resume(command, a_slice),
        )

    def _resume(self, command: ResumeImplementationCommand, a_slice: Slice) -> AgentRun | None:
        resumed = self._agent_runner.resume(command.run_id, self._recovery.resumption(a_slice))
        if resumed is not None:
            return resumed

        return self._recovery.redispatch(
            a_slice, command.run_id, command.workdir, command.repo, command.journal_enabled
        )

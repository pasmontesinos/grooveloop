from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.shared.domain.abandoned_agent_runs import AbandonedAgentRuns


@dataclass(frozen=True)
class CloseAgentRunCommand(Command):
    run_id: str


class CloseAgentRunCommandHandler(CommandHandler[CloseAgentRunCommand, None]):
    def __init__(self, abandoned_agent_runs: AbandonedAgentRuns) -> None:
        self._abandoned_agent_runs = abandoned_agent_runs

    def __call__(self, command: CloseAgentRunCommand) -> None:
        self._abandoned_agent_runs.close(command.run_id)

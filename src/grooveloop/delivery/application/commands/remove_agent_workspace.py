from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from collections.abc import Callable

    from grooveloop.shared.domain.agent_workspaces import AgentWorkspaces
    from grooveloop.shared.domain.workspace_containers import WorkspaceContainers
    from grooveloop.shared.domain.workspace_processes import WorkspaceProcesses


@dataclass(frozen=True)
class RemoveAgentWorkspaceCommand(Command):
    run_id: str


class RemoveAgentWorkspaceCommandHandler(CommandHandler[RemoveAgentWorkspaceCommand, None]):
    def __init__(
        self,
        agent_workspaces: AgentWorkspaces,
        workspace_processes: WorkspaceProcesses,
        workspace_containers: WorkspaceContainers,
    ) -> None:
        self._agent_workspaces = agent_workspaces
        self._workspace_processes = workspace_processes
        self._workspace_containers = workspace_containers

    def __call__(self, command: RemoveAgentWorkspaceCommand) -> None:
        workspace = self._agent_workspaces.workspace_of(command.run_id)
        if workspace is None:
            return

        failures = [
            failure
            for step in [self._workspace_processes.terminate, self._workspace_containers.remove]
            if (failure := _failure_of(step, workspace)) is not None
        ]

        self._agent_workspaces.remove(command.run_id)

        if failures:
            raise failures[0]


def _failure_of(step: Callable[[str], None], workspace: str) -> Exception | None:
    try:
        step(workspace)
    except Exception as error:
        return error

    return None

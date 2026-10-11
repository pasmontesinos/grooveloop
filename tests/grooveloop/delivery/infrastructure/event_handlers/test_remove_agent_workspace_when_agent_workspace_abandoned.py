from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.remove_agent_workspace import (
    RemoveAgentWorkspaceCommandHandler,
)
from grooveloop.delivery.domain.events import AgentWorkspaceAbandoned
from grooveloop.delivery.infrastructure.event_handlers.remove_agent_workspace_when_agent_workspace_abandoned import (
    RemoveAgentWorkspaceWhenAgentWorkspaceAbandoned,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(RemoveAgentWorkspaceCommandHandler, spec_set=True, instance=True)
    with container.override(RemoveAgentWorkspaceCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestRemoveAgentWorkspaceWhenAgentWorkspaceAbandoned:
    def test_invokes_the_command_with_the_run_id(self, command_handler: Mock) -> None:
        RemoveAgentWorkspaceWhenAgentWorkspaceAbandoned().handle(AgentWorkspaceAbandoned(run_id="run-1"))

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.run_id == "run-1"

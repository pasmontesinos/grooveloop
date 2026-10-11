from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.close_agent_run import CloseAgentRunCommandHandler
from grooveloop.delivery.domain.events import AgentRunAbandoned
from grooveloop.delivery.infrastructure.event_handlers.close_agent_run_when_agent_run_abandoned import (
    CloseAgentRunWhenAgentRunAbandoned,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(CloseAgentRunCommandHandler, spec_set=True, instance=True)
    with container.override(CloseAgentRunCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestCloseAgentRunWhenAgentRunAbandoned:
    def test_invokes_the_command_with_the_run_id(self, command_handler: Mock) -> None:
        CloseAgentRunWhenAgentRunAbandoned().handle(AgentRunAbandoned(run_id="run-1"))

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.run_id == "run-1"

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.block_slice import BlockSliceCommandHandler
from grooveloop.delivery.domain.events import HumanDecisionRequired
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.event_handlers.block_slice_when_human_decision_required import (
    BlockSliceWhenHumanDecisionRequired,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(BlockSliceCommandHandler, spec_set=True, instance=True)
    with container.override(BlockSliceCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestBlockSliceWhenHumanDecisionRequired:
    def test_invokes_the_command_with_the_slice_id(self, command_handler: Mock) -> None:
        BlockSliceWhenHumanDecisionRequired().handle(HumanDecisionRequired(slice_id=SliceId("12")))

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.slice_id == "12"

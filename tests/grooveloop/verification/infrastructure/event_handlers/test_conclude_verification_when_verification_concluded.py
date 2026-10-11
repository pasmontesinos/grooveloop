from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.verification.application.commands.conclude_verification import ConcludeVerificationCommandHandler
from grooveloop.verification.domain.events import VerificationConcluded
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.infrastructure.event_handlers.conclude_verification_when_verification_concluded import (
    ConcludeVerificationWhenVerificationConcluded,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(ConcludeVerificationCommandHandler, spec_set=True, instance=True)
    with container.override(ConcludeVerificationCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestConcludeVerificationWhenVerificationConcluded:
    def test_invokes_the_command_with_the_slice(self, command_handler: Mock) -> None:
        ConcludeVerificationWhenVerificationConcluded().handle(VerificationConcluded(slice_id=SliceId("11")))

        command_handler.assert_called_once()
        assert command_handler.call_args.args[0].slice_id == "11"

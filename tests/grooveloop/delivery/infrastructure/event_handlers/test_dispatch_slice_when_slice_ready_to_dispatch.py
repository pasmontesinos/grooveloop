from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.dispatch_slice import DispatchSliceCommandHandler
from grooveloop.delivery.domain.events import SliceReadyToDispatch
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.event_handlers.dispatch_slice_when_slice_ready_to_dispatch import (
    DispatchSliceWhenSliceReadyToDispatch,
)
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.delivery.infrastructure.max_parallel_slices import MaxParallelSlices
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(DispatchSliceCommandHandler, spec_set=True, instance=True)
    with container.override(DispatchSliceCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestDispatchSliceWhenSliceReadyToDispatch:
    def test_invokes_the_command_with_the_slice_id_workdir_repo_and_max_parallel_slices(
        self, command_handler: Mock
    ) -> None:
        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
            container.override(MaxParallelSlices, MaxParallelSlices(2)),
            container.override(JournalEnabled, JournalEnabled(False)),
        ):
            DispatchSliceWhenSliceReadyToDispatch().handle(SliceReadyToDispatch(slice_id=SliceId("12")))

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.slice_id == "12"
        assert command.workdir == "/tmp/wd"
        assert command.repo == "owner/repo"
        assert command.max_parallel_slices == 2

    def test_invokes_the_command_with_the_journal_enabled_flag(self, command_handler: Mock) -> None:
        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
            container.override(MaxParallelSlices, MaxParallelSlices(1)),
            container.override(JournalEnabled, JournalEnabled(True)),
        ):
            DispatchSliceWhenSliceReadyToDispatch().handle(SliceReadyToDispatch(slice_id=SliceId("12")))

        command = command_handler.call_args.args[0]
        assert command.journal_enabled is True

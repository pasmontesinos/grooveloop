from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.relaunch_review_phase import (
    RelaunchReviewPhaseCommand,
    RelaunchReviewPhaseCommandHandler,
)
from grooveloop.delivery.domain.events import ReviewPhaseInterrupted
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.event_handlers.relaunch_review_phase_when_review_phase_interrupted import (
    RelaunchReviewPhaseWhenReviewPhaseInterrupted,
)
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(RelaunchReviewPhaseCommandHandler, spec_set=True, instance=True)
    with container.override(RelaunchReviewPhaseCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestRelaunchReviewPhaseWhenReviewPhaseInterrupted:
    def test_invokes_the_command_with_the_interrupted_run_and_the_invocation_inputs(
        self, command_handler: Mock
    ) -> None:
        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
            container.override(MaxRetries, MaxRetries(2)),
            container.override(JournalEnabled, JournalEnabled(True)),
        ):
            RelaunchReviewPhaseWhenReviewPhaseInterrupted().handle(
                ReviewPhaseInterrupted(slice_id=SliceId("12"), run_id="run-1")
            )

        command_handler.assert_called_once()
        assert command_handler.call_args.args[0] == (
            RelaunchReviewPhaseCommand(
                slice_id="12",
                run_id="run-1",
                workdir="/tmp/wd",
                repo="owner/repo",
                max_retries=2,
                journal_enabled=True,
            )
        )

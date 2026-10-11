from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.max_retries import MaxRetries
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.verification.application.commands.recover_verification import (
    RecoverVerificationCommand,
    RecoverVerificationCommandHandler,
)
from grooveloop.verification.domain.events import VerificationRunFailed
from grooveloop.verification.domain.pull_request_number import PullRequestNumber
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.infrastructure.event_handlers.recover_verification_when_verification_run_failed import (
    RecoverVerificationWhenVerificationRunFailed,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(RecoverVerificationCommandHandler, spec_set=True, instance=True)
    with container.override(RecoverVerificationCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestRecoverVerificationWhenVerificationRunFailed:
    def test_invokes_the_command_with_the_failed_run_and_the_invocation_inputs(self, command_handler: Mock) -> None:
        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
            container.override(MaxRetries, MaxRetries(2)),
        ):
            RecoverVerificationWhenVerificationRunFailed().handle(
                VerificationRunFailed(
                    slice_id=SliceId("11"),
                    run_id="run-1",
                    pull_request_number=PullRequestNumber(42),
                    title="Mark verify-deploy",
                    description="the slice",
                )
            )

        command_handler.assert_called_once()
        assert command_handler.call_args.args[0] == RecoverVerificationCommand(
            slice_id="11",
            run_id="run-1",
            pull_request_number=42,
            title="Mark verify-deploy",
            description="the slice",
            workdir="/tmp/wd",
            repo="owner/repo",
            max_retries=2,
        )

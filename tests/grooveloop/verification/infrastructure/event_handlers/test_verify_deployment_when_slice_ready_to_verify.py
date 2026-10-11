from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.verification.application.commands.verify_deployment import VerifyDeploymentCommandHandler
from grooveloop.verification.domain.events import SliceReadyToVerify
from grooveloop.verification.domain.pull_request_number import PullRequestNumber
from grooveloop.verification.domain.slice_id import SliceId
from grooveloop.verification.infrastructure.event_handlers.verify_deployment_when_slice_ready_to_verify import (
    VerifyDeploymentWhenSliceReadyToVerify,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(VerifyDeploymentCommandHandler, spec_set=True, instance=True)
    with container.override(VerifyDeploymentCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestVerifyDeploymentWhenSliceReadyToVerify:
    def test_invokes_the_command_with_the_slice_pull_request_workdir_and_repo(self, command_handler: Mock) -> None:
        event = SliceReadyToVerify(
            slice_id=SliceId("11"),
            pull_request_number=PullRequestNumber(42),
            title="Mark verify-deploy when creating the sub-issues",
            description="- **Observable verification:**\n\n  1. `gh pr view 42`.\n",
        )

        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
        ):
            VerifyDeploymentWhenSliceReadyToVerify().handle(event)

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.slice_id == "11"
        assert command.pull_request_number == 42
        assert command.title == "Mark verify-deploy when creating the sub-issues"
        assert command.description == event.description
        assert command.workdir == "/tmp/wd"
        assert command.repo == "owner/repo"

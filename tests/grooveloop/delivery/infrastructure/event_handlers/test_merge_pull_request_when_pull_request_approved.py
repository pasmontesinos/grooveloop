from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.merge_pull_request import (
    MergePullRequestCommandHandler,
)
from grooveloop.delivery.domain.events import PullRequestApproved
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.event_handlers.merge_pull_request_when_pull_request_approved import (
    MergePullRequestWhenPullRequestApproved,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(MergePullRequestCommandHandler, spec_set=True, instance=True)
    with container.override(MergePullRequestCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestMergePullRequestWhenPullRequestApproved:
    def test_invokes_the_command_with_the_slice_id(self, command_handler: Mock) -> None:
        MergePullRequestWhenPullRequestApproved().handle(PullRequestApproved(slice_id=SliceId("12")))

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.slice_id == "12"

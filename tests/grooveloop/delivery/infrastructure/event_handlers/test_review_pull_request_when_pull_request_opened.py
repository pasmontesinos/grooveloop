from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.review_pull_request import (
    ReviewPullRequestCommandHandler,
)
from grooveloop.delivery.domain.events import PullRequestOpened
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.event_handlers.review_pull_request_when_pull_request_opened import (
    ReviewPullRequestWhenPullRequestOpened,
)
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(ReviewPullRequestCommandHandler, spec_set=True, instance=True)
    with container.override(ReviewPullRequestCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestReviewPullRequestWhenPullRequestOpened:
    def test_invokes_the_command_with_slice_pr_workdir_and_repo(self, command_handler: Mock) -> None:
        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
            container.override(JournalEnabled, JournalEnabled(False)),
        ):
            ReviewPullRequestWhenPullRequestOpened().handle(
                PullRequestOpened(slice_id=SliceId("12"), pull_request_number=PullRequestNumber(99))
            )

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.slice_id == "12"
        assert command.pull_request_number == 99
        assert command.workdir == "/tmp/wd"
        assert command.repo == "owner/repo"

    def test_invokes_the_command_with_the_journal_enabled_flag(self, command_handler: Mock) -> None:
        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
            container.override(JournalEnabled, JournalEnabled(True)),
        ):
            ReviewPullRequestWhenPullRequestOpened().handle(
                PullRequestOpened(slice_id=SliceId("12"), pull_request_number=PullRequestNumber(99))
            )

        command = command_handler.call_args.args[0]
        assert command.journal_enabled is True

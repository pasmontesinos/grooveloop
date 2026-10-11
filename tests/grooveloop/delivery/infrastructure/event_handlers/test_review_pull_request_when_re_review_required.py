from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.review_pull_request import ReviewPullRequestCommandHandler
from grooveloop.delivery.domain.events import ReReviewRequired
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.event_handlers.review_pull_request_when_re_review_required import (
    ReviewPullRequestWhenReReviewRequired,
)
from grooveloop.delivery.infrastructure.journal_enabled import JournalEnabled
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(ReviewPullRequestCommandHandler, spec_set=True, instance=True)
    with (
        container.override(ReviewPullRequestCommandHandler, mock),
        container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
        container.override(TargetRepo, TargetRepo("owner/repo")),
        container.override(JournalEnabled, JournalEnabled(False)),
    ):
        yield mock


@pytest.mark.entrypoint
class TestReviewPullRequestWhenReReviewRequired:
    def test_invokes_the_command_with_the_slice_and_its_pull_request(self, command_handler: Mock) -> None:
        ReviewPullRequestWhenReReviewRequired().handle(
            ReReviewRequired(slice_id=SliceId("12"), pull_request_number=PullRequestNumber(42))
        )

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.slice_id == "12"
        assert command.pull_request_number == 42
        assert command.workdir == "/tmp/wd"
        assert command.repo == "owner/repo"

    def test_invokes_the_command_with_the_journal_enabled_flag(self, command_handler: Mock) -> None:
        with container.override(JournalEnabled, JournalEnabled(True)):
            ReviewPullRequestWhenReReviewRequired().handle(
                ReReviewRequired(slice_id=SliceId("12"), pull_request_number=PullRequestNumber(42))
            )

        command = command_handler.call_args.args[0]
        assert command.journal_enabled is True

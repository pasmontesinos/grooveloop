from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.delivery.application.commands.address_review_changes import (
    AddressReviewChangesCommandHandler,
)
from grooveloop.delivery.domain.events import BlockingReviewDetected
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.infrastructure.event_handlers.address_review_changes_when_blocking_review_detected import (
    AddressReviewChangesWhenBlockingReviewDetected,
)
from grooveloop.delivery.infrastructure.max_review_rounds import MaxReviewRounds
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(AddressReviewChangesCommandHandler, spec_set=True, instance=True)
    with container.override(AddressReviewChangesCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestAddressReviewChangesWhenBlockingReviewDetected:
    def test_invokes_the_command_with_the_slice_id_workdir_repo_and_review_round_budget(
        self, command_handler: Mock
    ) -> None:
        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
            container.override(MaxReviewRounds, MaxReviewRounds(2)),
        ):
            AddressReviewChangesWhenBlockingReviewDetected().handle(BlockingReviewDetected(slice_id=SliceId("12")))

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.slice_id == "12"
        assert command.workdir == "/tmp/wd"
        assert command.repo == "owner/repo"
        assert command.automatic is True
        assert command.max_review_rounds == 2

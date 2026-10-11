from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.slicing.application.commands.create_slices_from_spec import CreateSlicesFromSpecCommandHandler
from grooveloop.slicing.domain.events import StoryReadyToSlice
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.infrastructure.event_handlers.create_slices_from_spec_when_story_ready_to_slice import (
    CreateSlicesFromSpecWhenStoryReadyToSlice,
)
from grooveloop.slicing.infrastructure.verify_deploy import VerifyDeploy

if TYPE_CHECKING:
    from collections.abc import Iterator
    from unittest.mock import Mock


@pytest.fixture(autouse=True)
def _deploy_verification_disabled() -> Iterator[None]:
    with container.override(VerifyDeploy, VerifyDeploy(False)):
        yield


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(CreateSlicesFromSpecCommandHandler, spec_set=True, instance=True)
    with container.override(CreateSlicesFromSpecCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestCreateSlicesFromSpecWhenStoryReadyToSlice:
    def test_invokes_the_command_with_the_story_id(self, command_handler: Mock) -> None:
        CreateSlicesFromSpecWhenStoryReadyToSlice().handle(StoryReadyToSlice(story_id=StoryId("7")))

        command_handler.assert_called_once()
        assert command_handler.call_args.args[0].story_id == "7"

    def test_asks_for_deploy_verification_when_the_container_enables_it(self, command_handler: Mock) -> None:
        with container.override(VerifyDeploy, VerifyDeploy(True)):
            CreateSlicesFromSpecWhenStoryReadyToSlice().handle(StoryReadyToSlice(story_id=StoryId("7")))

        assert command_handler.call_args.args[0].verify_deploy is True

    def test_does_not_ask_for_deploy_verification_when_the_container_disables_it(self, command_handler: Mock) -> None:
        CreateSlicesFromSpecWhenStoryReadyToSlice().handle(StoryReadyToSlice(story_id=StoryId("7")))

        assert command_handler.call_args.args[0].verify_deploy is False

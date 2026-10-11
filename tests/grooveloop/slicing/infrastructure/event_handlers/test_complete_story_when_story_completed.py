from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.slicing.application.commands.complete_story import CompleteStoryCommandHandler
from grooveloop.slicing.domain.events import StoryCompleted
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.infrastructure.event_handlers.complete_story_when_story_completed import (
    CompleteStoryWhenStoryCompleted,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(CompleteStoryCommandHandler, spec_set=True, instance=True)
    with container.override(CompleteStoryCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestCompleteStoryWhenStoryCompleted:
    def test_invokes_the_command_with_the_story_id(self, command_handler: Mock) -> None:
        CompleteStoryWhenStoryCompleted().handle(StoryCompleted(story_id=StoryId("7")))

        command_handler.assert_called_once()
        assert command_handler.call_args.args[0].story_id == "7"

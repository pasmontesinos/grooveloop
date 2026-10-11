from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.learning.application.commands.discard_lesson import DiscardLessonCommandHandler
from grooveloop.learning.domain.events import LessonDiscarded
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.event_handlers.discard_lesson_when_lesson_discarded import (
    DiscardLessonWhenLessonDiscarded,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(DiscardLessonCommandHandler, spec_set=True, instance=True)
    with container.override(DiscardLessonCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestDiscardLessonWhenLessonDiscarded:
    def test_invokes_the_command_with_the_source_pull_request(self, command_handler: Mock) -> None:
        event = LessonDiscarded(source_pull_request=SourcePullRequest(42), story_id=StoryId("277"))

        DiscardLessonWhenLessonDiscarded().handle(event)

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.source_pull_request == 42

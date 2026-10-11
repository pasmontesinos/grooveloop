from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.learning.application.commands.close_lesson import CloseLessonCommandHandler
from grooveloop.learning.domain.events import LessonResolved
from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.event_handlers.close_lesson_when_lesson_resolved import (
    CloseLessonWhenLessonResolved,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(CloseLessonCommandHandler, spec_set=True, instance=True)
    with container.override(CloseLessonCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestCloseLessonWhenLessonResolved:
    def test_invokes_the_command_with_the_lesson_id(self, command_handler: Mock) -> None:
        event = LessonResolved(lesson_id=LessonId("500"), story_id=StoryId("277"))

        CloseLessonWhenLessonResolved().handle(event)

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.lesson_id == "500"

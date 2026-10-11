from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.learning.application.commands.learn_lesson import LearnLessonCommandHandler
from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest
from grooveloop.learning.domain.events import LessonLearned
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.event_handlers.learn_lesson_when_lesson_learned import (
    LearnLessonWhenLessonLearned,
)

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(LearnLessonCommandHandler, spec_set=True, instance=True)
    with container.override(LearnLessonCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestLearnLessonWhenLessonLearned:
    def test_invokes_the_command_with_the_source_and_conventions_pull_requests(self, command_handler: Mock) -> None:
        event = LessonLearned(
            source_pull_request=SourcePullRequest(42),
            story_id=StoryId("277"),
            conventions_pull_request=ConventionsPullRequest(101),
        )

        LearnLessonWhenLessonLearned().handle(event)

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.source_pull_request == 42
        assert command.conventions_pull_request == 101

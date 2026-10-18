from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.learning.application.commands.refine_conventions import RefineConventionsCommandHandler
from grooveloop.learning.domain.events import LessonCaptured
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.event_handlers.refine_conventions_when_lesson_captured import (
    RefineConventionsWhenLessonCaptured,
)
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo

if TYPE_CHECKING:
    from unittest.mock import Mock


@pytest.fixture
def command_handler() -> Any:
    mock = create_autospec(RefineConventionsCommandHandler, spec_set=True, instance=True)
    with container.override(RefineConventionsCommandHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestRefineConventionsWhenLessonCaptured:
    def test_invokes_the_command_with_the_aggregated_comments_workdir_and_repo(self, command_handler: Mock) -> None:
        event = LessonCaptured(
            source_pull_request=SourcePullRequest(42),
            story_id=StoryId("277"),
            comments=[
                LessonComment(
                    body="/grooveloop-learn: inject through the constructor",
                    path="src/x.py",
                    line=10,
                    diff_hunk="@@ @@",
                    id="IC_1",
                ),
            ],
        )

        with (
            container.override(AgentWorkdir, AgentWorkdir("/tmp/wd")),
            container.override(TargetRepo, TargetRepo("owner/repo")),
        ):
            RefineConventionsWhenLessonCaptured().handle(event)

        command_handler.assert_called_once()
        command = command_handler.call_args.args[0]
        assert command.source_pull_request == 42
        assert command.story_id == "277"
        assert command.comments == [
            {
                "body": "/grooveloop-learn: inject through the constructor",
                "path": "src/x.py",
                "line": 10,
                "diff_hunk": "@@ @@",
                "id": "IC_1",
            }
        ]
        assert command.workdir == "/tmp/wd"
        assert command.repo == "owner/repo"

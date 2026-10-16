from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.learning.application.commands.refine_conventions import (
    RefineConventionsCommand,
    RefineConventionsCommandHandler,
)
from grooveloop.learning.domain.events import LessonCaptured
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.target_repo import TargetRepo


class RefineConventionsWhenLessonCaptured(EventHandler[LessonCaptured]):
    event_class = LessonCaptured

    def handle(self, event: LessonCaptured) -> None:
        handler = container.get(RefineConventionsCommandHandler)
        workdir = container.get(AgentWorkdir)
        repo = container.get(TargetRepo)

        handler(
            RefineConventionsCommand(
                source_pull_request=event.source_pull_request.value,
                story_id=event.story_id.value,
                comments=[
                    {
                        "body": comment.body,
                        "path": comment.path,
                        "line": comment.line,
                        "diff_hunk": comment.diff_hunk,
                        "id": comment.id,
                        "written_at": comment.written_at,
                    }
                    for comment in event.comments
                ],
                workdir=workdir.value,
                repo=repo.value,
            )
        )

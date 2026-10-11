from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.learning.application.commands.discard_lesson import DiscardLessonCommand, DiscardLessonCommandHandler
from grooveloop.learning.domain.events import LessonDiscarded
from grooveloop.shared.application.events.event_handler import EventHandler


class DiscardLessonWhenLessonDiscarded(EventHandler[LessonDiscarded]):
    event_class = LessonDiscarded

    def handle(self, event: LessonDiscarded) -> None:
        handler = container.get(DiscardLessonCommandHandler)

        handler(DiscardLessonCommand(source_pull_request=event.source_pull_request.value))

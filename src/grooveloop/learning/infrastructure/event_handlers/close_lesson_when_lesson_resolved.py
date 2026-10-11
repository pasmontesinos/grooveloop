from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.learning.application.commands.close_lesson import CloseLessonCommand, CloseLessonCommandHandler
from grooveloop.learning.domain.events import LessonResolved
from grooveloop.shared.application.events.event_handler import EventHandler


class CloseLessonWhenLessonResolved(EventHandler[LessonResolved]):
    event_class = LessonResolved

    def handle(self, event: LessonResolved) -> None:
        handler = container.get(CloseLessonCommandHandler)

        handler(CloseLessonCommand(lesson_id=event.lesson_id.value))

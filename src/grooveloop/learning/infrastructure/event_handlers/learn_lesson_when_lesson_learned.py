from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.learning.application.commands.learn_lesson import LearnLessonCommand, LearnLessonCommandHandler
from grooveloop.learning.domain.events import LessonLearned
from grooveloop.shared.application.events.event_handler import EventHandler


class LearnLessonWhenLessonLearned(EventHandler[LessonLearned]):
    event_class = LessonLearned

    def handle(self, event: LessonLearned) -> None:
        handler = container.get(LearnLessonCommandHandler)

        handler(
            LearnLessonCommand(
                source_pull_request=event.source_pull_request.value,
                conventions_pull_request=event.conventions_pull_request.value,
            )
        )

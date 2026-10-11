from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.slicing.application.commands.complete_story import (
    CompleteStoryCommand,
    CompleteStoryCommandHandler,
)
from grooveloop.slicing.domain.events import StoryCompleted


class CompleteStoryWhenStoryCompleted(EventHandler[StoryCompleted]):
    event_class = StoryCompleted

    def handle(self, event: StoryCompleted) -> None:
        handler = container.get(CompleteStoryCommandHandler)

        handler(CompleteStoryCommand(story_id=event.story_id.value))

from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.shared.application.events.event_handler import EventHandler
from grooveloop.slicing.application.commands.create_slices_from_spec import (
    CreateSlicesFromSpecCommand,
    CreateSlicesFromSpecCommandHandler,
)
from grooveloop.slicing.domain.events import StoryReadyToSlice
from grooveloop.slicing.infrastructure.verify_deploy import VerifyDeploy


class CreateSlicesFromSpecWhenStoryReadyToSlice(EventHandler[StoryReadyToSlice]):
    event_class = StoryReadyToSlice

    def handle(self, event: StoryReadyToSlice) -> None:
        handler = container.get(CreateSlicesFromSpecCommandHandler)
        verify_deploy = container.get(VerifyDeploy)

        handler(CreateSlicesFromSpecCommand(story_id=event.story_id.value, verify_deploy=verify_deploy.value))

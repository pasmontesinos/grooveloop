from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler
from grooveloop.slicing.domain.exceptions import StoryNotFoundError
from grooveloop.slicing.domain.story_id import StoryId

if TYPE_CHECKING:
    from grooveloop.slicing.domain.story_repository import StoryRepository


@dataclass(frozen=True)
class CompleteStoryCommand(Command):
    story_id: str


class CompleteStoryCommandHandler(CommandHandler[CompleteStoryCommand, None]):
    def __init__(self, story_repository: StoryRepository) -> None:
        self._story_repository = story_repository

    def __call__(self, command: CompleteStoryCommand) -> None:
        story = self._story_repository.find(StoryId(command.story_id))
        if story is None:
            raise StoryNotFoundError(f"Story {command.story_id} not found")

        story.complete()

        self._story_repository.save(story)

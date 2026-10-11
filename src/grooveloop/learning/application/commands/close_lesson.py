from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.learning.domain.lesson_id import LessonId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_repository import LessonRepository


@dataclass(frozen=True)
class CloseLessonCommand(Command):
    lesson_id: str


class CloseLessonCommandHandler(CommandHandler[CloseLessonCommand, None]):
    def __init__(self, lesson_repository: LessonRepository) -> None:
        self._lesson_repository = lesson_repository

    def __call__(self, command: CloseLessonCommand) -> None:
        lesson = self._lesson_repository.find(LessonId(command.lesson_id))
        if lesson is None or not lesson.is_open:
            return

        lesson.close()

        self._lesson_repository.save(lesson)

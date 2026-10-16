from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.learning.domain.lesson_status import LessonStatus
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_repository import LessonRepository


@dataclass(frozen=True)
class DiscardLessonCommand(Command):
    source_pull_request: int


class DiscardLessonCommandHandler(CommandHandler[DiscardLessonCommand, None]):
    def __init__(self, lesson_repository: LessonRepository) -> None:
        self._lesson_repository = lesson_repository

    def __call__(self, command: DiscardLessonCommand) -> None:
        lessons = self._lesson_repository.search(
            status=LessonStatus.IN_PROGRESS, source_pull_request=SourcePullRequest(command.source_pull_request)
        )
        if not lessons:
            return

        lesson = lessons[0]
        lesson.discard()

        self._lesson_repository.save(lesson)

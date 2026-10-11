from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.journal.domain.journal_entry import JournalEntry
from grooveloop.journal.domain.story_id import StoryId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.journal.domain.journal_entry_repository import JournalEntryRepository
    from grooveloop.shared.domain.clock import Clock


@dataclass(frozen=True)
class AppendJournalEntryCommand(Command):
    repo: str
    story_id: str
    kind: str
    author: str
    body: str


class AppendJournalEntryCommandHandler(CommandHandler[AppendJournalEntryCommand, None]):
    def __init__(self, journal_entry_repository: JournalEntryRepository, clock: Clock) -> None:
        self._journal_entry_repository = journal_entry_repository
        self._clock = clock

    def __call__(self, command: AppendJournalEntryCommand) -> None:
        entry = JournalEntry.write(
            repo=command.repo,
            story_id=StoryId(command.story_id),
            kind=EntryKind(command.kind),
            author=command.author,
            body=command.body,
            written_at=self._clock.now(),
        )

        self._journal_entry_repository.save(entry)

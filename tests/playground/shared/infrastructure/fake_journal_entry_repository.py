from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.journal.domain.journal_entry_repository import JournalEntryRepository

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.journal.domain.entry_kind import EntryKind
    from grooveloop.journal.domain.journal_entry import JournalEntry
    from grooveloop.journal.domain.story_id import StoryId


class FakeJournalEntryRepository(JournalEntryRepository):
    def __init__(self) -> None:
        self.saved: list[JournalEntry] = []

    def save(self, entry: JournalEntry) -> None:
        self.saved.append(entry)

    def search(
        self,
        repo: str,
        story_id: StoryId | None = None,
        kind: list[EntryKind] | None = None,
        written_after: datetime | None = None,
    ) -> list[JournalEntry]:
        entries = [entry for entry in self.saved if entry.repo == repo]
        if story_id is not None:
            entries = [entry for entry in entries if entry.story_id == story_id]
        if kind is not None:
            entries = [entry for entry in entries if entry.kind in kind]
        if written_after is not None:
            entries = [entry for entry in entries if entry.written_at > written_after]

        return entries

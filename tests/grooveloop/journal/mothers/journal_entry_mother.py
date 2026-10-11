from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.journal.domain.journal_entry import JournalEntry
from grooveloop.journal.domain.journal_entry_id import JournalEntryId
from grooveloop.journal.domain.story_id import StoryId

_WRITTEN_AT = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


class JournalEntryMother:
    @staticmethod
    def create(
        entry_id: str | None = None,
        repo: str = "acme/playground",
        story_id: str = "999",
        kind: EntryKind = EntryKind.FINDING,
        author: str = "human",
        body: str = "the fixture does not clean the DB",
        written_at: datetime = _WRITTEN_AT,
    ) -> JournalEntry:
        return JournalEntry(
            id=JournalEntryId(entry_id) if entry_id is not None else JournalEntryId.generate(),
            repo=repo,
            story_id=StoryId(story_id),
            kind=kind,
            author=author,
            body=body,
            written_at=written_at,
        )

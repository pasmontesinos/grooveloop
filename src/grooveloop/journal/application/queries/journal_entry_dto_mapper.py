from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.read_journal_entries import JournalEntryDTO

if TYPE_CHECKING:
    from grooveloop.journal.domain.journal_entry import JournalEntry


def journal_entry_dto_from_domain(entry: JournalEntry) -> JournalEntryDTO:
    return JournalEntryDTO(
        kind=entry.kind.value,
        author=entry.author,
        body=entry.body,
        written_at=entry.written_at.isoformat(),
    )

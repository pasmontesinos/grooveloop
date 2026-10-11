from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.journal.application.queries.journal_entry_dto_mapper import journal_entry_dto_from_domain
from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.journal.domain.story_id import StoryId
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.shared.application.queries.read_journal_entries import (
    ReadJournalEntriesQuery,
    ReadJournalEntriesQueryResult,
)

if TYPE_CHECKING:
    from grooveloop.journal.domain.journal_entry_repository import JournalEntryRepository


class ReadJournalEntriesQueryHandler(QueryHandler[ReadJournalEntriesQuery, ReadJournalEntriesQueryResult]):
    def __init__(self, journal_entry_repository: JournalEntryRepository) -> None:
        self._journal_entry_repository = journal_entry_repository

    def __call__(self, query: ReadJournalEntriesQuery) -> ReadJournalEntriesQueryResult:
        kind = [EntryKind(value) for value in query.kinds] if query.kinds is not None else None
        entries = self._journal_entry_repository.search(
            repo=query.repo, story_id=StoryId(query.story_id), kind=kind, written_after=query.written_after
        )

        return ReadJournalEntriesQueryResult(entries=[journal_entry_dto_from_domain(entry) for entry in entries])

from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.journal.application.queries.read_journal_entries import ReadJournalEntriesQueryHandler
from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.shared.application.queries.read_journal_entries import ReadJournalEntriesQuery
from tests.grooveloop.journal.mothers.journal_entry_mother import JournalEntryMother
from tests.playground.shared.infrastructure.fake_journal_entry_repository import FakeJournalEntryRepository

_WRITTEN_AT = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


class TestReadJournalEntriesQueryHandler:
    def test_should_return_the_entries_of_the_story_as_dtos(self) -> None:
        journal_entry_repository = FakeJournalEntryRepository()
        journal_entry_repository.save(
            JournalEntryMother.create(
                repo="acme/playground",
                story_id="999",
                kind=EntryKind.FINDING,
                author="human",
                body="the fixture does not clean the DB",
                written_at=_WRITTEN_AT,
            )
        )
        handler = ReadJournalEntriesQueryHandler(journal_entry_repository=journal_entry_repository)

        result = handler(ReadJournalEntriesQuery(repo="acme/playground", story_id="999"))

        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.kind == "finding"
        assert entry.author == "human"
        assert entry.body == "the fixture does not clean the DB"
        assert entry.written_at == _WRITTEN_AT.isoformat()

    def test_should_convert_the_requested_kinds_before_reaching_the_port(self) -> None:
        journal_entry_repository = FakeJournalEntryRepository()
        journal_entry_repository.save(
            JournalEntryMother.create(
                repo="acme/playground",
                story_id="999",
                kind=EntryKind.CONSTRAINT,
                author="human",
                body="do not touch the legacy client",
                written_at=_WRITTEN_AT,
            )
        )
        journal_entry_repository.save(
            JournalEntryMother.create(
                repo="acme/playground",
                story_id="999",
                kind=EntryKind.FINDING,
                author="human",
                body="the fixture does not clean the DB",
                written_at=_WRITTEN_AT,
            )
        )
        handler = ReadJournalEntriesQueryHandler(journal_entry_repository=journal_entry_repository)

        result = handler(ReadJournalEntriesQuery(repo="acme/playground", story_id="999", kinds=["constraint"]))

        assert [entry.kind for entry in result.entries] == ["constraint"]

    def test_should_return_no_entries_for_a_story_without_journal(self) -> None:
        journal_entry_repository = FakeJournalEntryRepository()
        handler = ReadJournalEntriesQueryHandler(journal_entry_repository=journal_entry_repository)

        result = handler(ReadJournalEntriesQuery(repo="acme/playground", story_id="1000"))

        assert result.entries == []

    def test_should_return_only_the_entries_written_after_the_requested_instant(self) -> None:
        journal_entry_repository = FakeJournalEntryRepository()
        journal_entry_repository.save(
            JournalEntryMother.create(
                repo="acme/playground",
                story_id="999",
                kind=EntryKind.CONSTRAINT,
                author="human",
                body="do not touch the legacy client",
                written_at=_WRITTEN_AT,
            )
        )
        journal_entry_repository.save(
            JournalEntryMother.create(
                repo="acme/playground",
                story_id="999",
                kind=EntryKind.DIRECTIVE,
                author="human",
                body="use the new client",
                written_at=datetime(2026, 9, 10, 13, 0, 0, tzinfo=UTC),
            )
        )
        handler = ReadJournalEntriesQueryHandler(journal_entry_repository=journal_entry_repository)

        result = handler(ReadJournalEntriesQuery(repo="acme/playground", story_id="999", written_after=_WRITTEN_AT))

        assert [entry.body for entry in result.entries] == ["use the new client"]

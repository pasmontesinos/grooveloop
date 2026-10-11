from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.journal.domain.journal_entry_id import JournalEntryId
from grooveloop.journal.domain.story_id import StoryId
from grooveloop.journal.infrastructure.filesystem_journal_entry_repository import (
    FilesystemJournalEntryRepository,
)
from tests.grooveloop.journal.mothers.journal_entry_mother import JournalEntryMother

if TYPE_CHECKING:
    from pathlib import Path

    from grooveloop.journal.domain.journal_entry import JournalEntry

_WRITTEN_AT = datetime(2026, 9, 10, 12, 0, 0, 123456, tzinfo=UTC)
_EARLIER = datetime(2026, 9, 10, 11, 0, 0, tzinfo=UTC)


def _seed(
    repos_dir: Path,
    story_id: str = "999",
    kind: str = "finding",
    body: str = "the fixture does not clean the DB",
    written_at: datetime = _WRITTEN_AT,
) -> None:
    journal_dir = repos_dir / "acme" / "playground" / "stories" / story_id / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    entry = {"kind": kind, "author": "human", "body": body, "story_id": story_id, "written_at": written_at.isoformat()}
    (journal_dir / f"{written_at.strftime('%Y%m%dT%H%M%S%f')}-human.json").write_text(json.dumps(entry))


def _entry(story_id: str = "999", kind: EntryKind = EntryKind.FINDING, author: str = "human") -> JournalEntry:
    return JournalEntryMother.create(
        entry_id="entry-1",
        repo="acme/playground",
        story_id=story_id,
        kind=kind,
        author=author,
        body="the fixture does not clean the DB",
        written_at=_WRITTEN_AT,
    )


@pytest.mark.integration
class TestFilesystemJournalEntryRepository:
    def test_should_write_one_file_under_the_story_journal_directory(self, tmp_path: Path) -> None:
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        repository.save(_entry())

        journal_dir = tmp_path / "acme" / "playground" / "stories" / "999" / "journal"
        assert len(list(journal_dir.iterdir())) == 1

    def test_should_store_kind_author_body_story_and_instant(self, tmp_path: Path) -> None:
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        repository.save(_entry())

        journal_dir = tmp_path / "acme" / "playground" / "stories" / "999" / "journal"
        stored = json.loads(next(journal_dir.iterdir()).read_text())
        assert stored == {
            "id": "entry-1",
            "kind": "finding",
            "author": "human",
            "body": "the fixture does not clean the DB",
            "story_id": "999",
            "written_at": _WRITTEN_AT.isoformat(),
        }

    def test_should_leave_no_partial_file_behind(self, tmp_path: Path) -> None:
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        repository.save(_entry())

        journal_dir = tmp_path / "acme" / "playground" / "stories" / "999" / "journal"
        assert all(not path.name.endswith(".tmp") for path in journal_dir.iterdir())

    def test_should_keep_each_entry_in_its_own_file_ordered_by_instant(self, tmp_path: Path) -> None:
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)
        earlier = JournalEntryMother.create(
            repo="acme/playground",
            story_id="999",
            kind=EntryKind.CONSTRAINT,
            author="human",
            body="do not touch the legacy client",
            written_at=datetime(2026, 9, 10, 11, 0, 0, tzinfo=UTC),
        )
        later = _entry()

        repository.save(later)
        repository.save(earlier)

        journal_dir = tmp_path / "acme" / "playground" / "stories" / "999" / "journal"
        filenames = sorted(path.name for path in journal_dir.iterdir())
        assert len(filenames) == 2
        assert filenames[0].startswith(earlier.written_at.strftime("%Y%m%dT%H%M%S"))
        assert filenames[1].startswith(later.written_at.strftime("%Y%m%dT%H%M%S"))

    def test_should_read_back_the_id_of_a_saved_entry(self, tmp_path: Path) -> None:
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)
        repository.save(_entry())

        entries = repository.search(repo="acme/playground", story_id=StoryId("999"))

        assert [entry.id for entry in entries] == [JournalEntryId("entry-1")]

    def test_should_give_an_entry_stored_without_id_the_same_id_on_every_read(self, tmp_path: Path) -> None:
        _seed(tmp_path, story_id="999")
        _seed(tmp_path, story_id="1000")
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        first = [entry.id for entry in repository.search(repo="acme/playground")]
        second = [entry.id for entry in repository.search(repo="acme/playground")]

        assert first == second
        assert len(set(first)) == 2

    def test_should_return_no_entries_when_the_story_has_no_journal_directory(self, tmp_path: Path) -> None:
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        entries = repository.search(repo="acme/playground", story_id=StoryId("999"))

        assert entries == []

    def test_should_return_entries_ordered_by_instant(self, tmp_path: Path) -> None:
        _seed(tmp_path, body="the fixture does not clean the DB", written_at=_WRITTEN_AT)
        _seed(tmp_path, kind="constraint", body="do not touch the legacy client", written_at=_EARLIER)
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        entries = repository.search(repo="acme/playground", story_id=StoryId("999"))

        assert [entry.body for entry in entries] == [
            "do not touch the legacy client",
            "the fixture does not clean the DB",
        ]

    def test_should_filter_by_kind(self, tmp_path: Path) -> None:
        _seed(tmp_path, kind="finding", written_at=_WRITTEN_AT)
        _seed(tmp_path, kind="constraint", written_at=_EARLIER)
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        entries = repository.search(repo="acme/playground", story_id=StoryId("999"), kind=[EntryKind.CONSTRAINT])

        assert [entry.kind for entry in entries] == [EntryKind.CONSTRAINT]

    def test_should_not_leak_entries_from_another_story(self, tmp_path: Path) -> None:
        _seed(tmp_path, story_id="999")
        _seed(tmp_path, story_id="1000")
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        entries = repository.search(repo="acme/playground", story_id=StoryId("1000"))

        assert len(entries) == 1

    def test_should_return_the_entries_of_every_story_without_the_story_criterion(self, tmp_path: Path) -> None:
        _seed(tmp_path, story_id="1000", written_at=_WRITTEN_AT)
        _seed(tmp_path, story_id="999", written_at=_EARLIER)
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        entries = repository.search(repo="acme/playground")

        assert [entry.story_id for entry in entries] == [StoryId("999"), StoryId("1000")]

    def test_should_return_only_the_entries_written_after_the_given_instant(self, tmp_path: Path) -> None:
        _seed(tmp_path, written_at=_EARLIER)
        _seed(tmp_path, written_at=_WRITTEN_AT)
        repository = FilesystemJournalEntryRepository(repos_dir=tmp_path)

        entries = repository.search(repo="acme/playground", story_id=StoryId("999"), written_after=_EARLIER)

        assert [entry.written_at for entry in entries] == [_WRITTEN_AT]

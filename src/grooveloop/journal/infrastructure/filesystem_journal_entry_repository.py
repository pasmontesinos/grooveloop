from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.journal.domain.journal_entry import JournalEntry
from grooveloop.journal.domain.journal_entry_id import JournalEntryId
from grooveloop.journal.domain.journal_entry_repository import JournalEntryRepository
from grooveloop.journal.domain.story_id import StoryId

if TYPE_CHECKING:
    from pathlib import Path

_ANY_STORY = "*"


class FilesystemJournalEntryRepository(JournalEntryRepository):
    def __init__(self, repos_dir: Path) -> None:
        self._repos_dir = repos_dir

    def save(self, entry: JournalEntry) -> None:
        journal_dir = self._journal_dir(entry.repo, entry.story_id.value)
        journal_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{entry.written_at.strftime('%Y%m%dT%H%M%S%f')}-{entry.author}.json"
        pending = journal_dir / f"{filename}.tmp"
        pending.write_text(json.dumps(_to_json(entry)))
        os.replace(pending, journal_dir / filename)

    def search(
        self,
        repo: str,
        story_id: StoryId | None = None,
        kind: list[EntryKind] | None = None,
        written_after: datetime | None = None,
    ) -> list[JournalEntry]:
        story = _ANY_STORY if story_id is None else story_id.value
        paths = sorted((self._repos_dir / repo / "stories").glob(f"{story}/journal/*.json"), key=lambda path: path.name)

        entries = [
            _from_json(json.loads(path.read_text()), repo=repo, legacy_id=self._legacy_id(path)) for path in paths
        ]
        if kind is not None:
            entries = [entry for entry in entries if entry.kind in kind]
        if written_after is not None:
            entries = [entry for entry in entries if entry.written_at > written_after]

        return entries

    def _legacy_id(self, path: Path) -> JournalEntryId:
        return JournalEntryId(str(uuid.uuid5(uuid.NAMESPACE_URL, path.relative_to(self._repos_dir).as_posix())))

    def _journal_dir(self, repo: str, story_id: str) -> Path:
        return self._repos_dir / repo / "stories" / story_id / "journal"


def _to_json(entry: JournalEntry) -> dict[str, Any]:
    return {
        "id": entry.id.value,
        "kind": entry.kind.value,
        "author": entry.author,
        "body": entry.body,
        "story_id": entry.story_id.value,
        "written_at": entry.written_at.isoformat(),
    }


def _from_json(data: dict[str, Any], repo: str, legacy_id: JournalEntryId) -> JournalEntry:
    return JournalEntry(
        id=JournalEntryId(data["id"]) if "id" in data else legacy_id,
        repo=repo,
        story_id=StoryId(data["story_id"]),
        kind=EntryKind(data["kind"]),
        author=data["author"],
        body=data["body"],
        written_at=datetime.fromisoformat(data["written_at"]),
    )

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from grooveloop.journal.domain.journal_entry_id import JournalEntryId

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.journal.domain.entry_kind import EntryKind
    from grooveloop.journal.domain.story_id import StoryId


class JournalEntry:
    def __init__(
        self,
        id: JournalEntryId,
        repo: str,
        story_id: StoryId,
        kind: EntryKind,
        author: str,
        body: str,
        written_at: datetime,
    ) -> None:
        self._id = id
        self._repo = repo
        self._story_id = story_id
        self._kind = kind
        self._author = author
        self._body = body
        self._written_at = written_at

    @classmethod
    def write(
        cls,
        repo: str,
        story_id: StoryId,
        kind: EntryKind,
        author: str,
        body: str,
        written_at: datetime,
    ) -> Self:
        return cls(
            id=JournalEntryId.generate(),
            repo=repo,
            story_id=story_id,
            kind=kind,
            author=author,
            body=body,
            written_at=written_at,
        )

    @property
    def id(self) -> JournalEntryId:
        return self._id

    @property
    def repo(self) -> str:
        return self._repo

    @property
    def story_id(self) -> StoryId:
        return self._story_id

    @property
    def kind(self) -> EntryKind:
        return self._kind

    @property
    def author(self) -> str:
        return self._author

    @property
    def body(self) -> str:
        return self._body

    @property
    def written_at(self) -> datetime:
        return self._written_at

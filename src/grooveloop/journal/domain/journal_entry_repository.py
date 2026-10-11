from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.journal.domain.entry_kind import EntryKind
    from grooveloop.journal.domain.journal_entry import JournalEntry
    from grooveloop.journal.domain.story_id import StoryId


class JournalEntryRepository(ABC):
    @abstractmethod
    def save(self, entry: JournalEntry) -> None: ...

    @abstractmethod
    def search(
        self,
        repo: str,
        story_id: StoryId | None = None,
        kind: list[EntryKind] | None = None,
        written_after: datetime | None = None,
    ) -> list[JournalEntry]: ...

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_result import QueryResult

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class JournalEntryDTO:
    kind: str
    author: str
    body: str
    written_at: str


@dataclass(frozen=True)
class ReadJournalEntriesQueryResult(QueryResult):
    entries: list[JournalEntryDTO]


@dataclass(frozen=True)
class ReadJournalEntriesQuery(Query[ReadJournalEntriesQueryResult]):
    repo: str
    story_id: str
    kinds: list[str] | None = None
    written_after: datetime | None = None

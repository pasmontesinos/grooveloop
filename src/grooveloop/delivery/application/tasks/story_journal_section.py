from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.read_journal_entries import (
    ReadJournalEntriesQuery,
)

if TYPE_CHECKING:
    from grooveloop.shared.application.queries.query_bus import QueryBus


class StoryJournalSection:
    def __init__(self, query_bus: QueryBus) -> None:
        self._query_bus = query_bus

    def build(self, repo: str, story_id: str) -> str:
        result = self._query_bus.ask(ReadJournalEntriesQuery(repo=repo, story_id=story_id))
        if not result.entries:
            return ""

        entries_text = "\n".join(
            f"- [{entry.kind}] {entry.written_at} {entry.author}: {entry.body}" for entry in result.entries
        )

        return f"## Story journal\n{entries_text}\n\n"

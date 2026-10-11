from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import create_autospec

import pytest

from grooveloop.journal.application.commands.append_journal_entry import (
    AppendJournalEntryCommand,
    AppendJournalEntryCommandHandler,
)
from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.journal.domain.story_id import StoryId
from grooveloop.shared.domain.clock import Clock
from tests.playground.shared.infrastructure.fake_journal_entry_repository import FakeJournalEntryRepository

_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


def _clock_frozen_at(now: datetime) -> Any:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = now

    return clock


class TestAppendJournalEntryCommandHandler:
    def test_should_save_an_entry_stamped_with_the_clock_instant(self) -> None:
        repository = FakeJournalEntryRepository()
        handler = AppendJournalEntryCommandHandler(journal_entry_repository=repository, clock=_clock_frozen_at(_NOW))

        handler(
            AppendJournalEntryCommand(
                repo="acme/playground",
                story_id="999",
                kind="finding",
                author="human",
                body="the fixture does not clean the DB",
            )
        )

        assert len(repository.saved) == 1
        saved = repository.saved[0]
        assert saved.repo == "acme/playground"
        assert saved.story_id == StoryId("999")
        assert saved.kind == EntryKind.FINDING
        assert saved.author == "human"
        assert saved.body == "the fixture does not clean the DB"
        assert saved.written_at == _NOW

    def test_should_raise_and_save_nothing_when_the_kind_is_unknown(self) -> None:
        repository = FakeJournalEntryRepository()
        handler = AppendJournalEntryCommandHandler(journal_entry_repository=repository, clock=_clock_frozen_at(_NOW))

        with pytest.raises(ValueError):
            handler(
                AppendJournalEntryCommand(
                    repo="acme/playground",
                    story_id="999",
                    kind="inventado",
                    author="human",
                    body="x",
                )
            )

        assert repository.saved == []

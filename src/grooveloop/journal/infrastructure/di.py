from __future__ import annotations

from injector import Binder, Module, provider

from grooveloop.journal.application.commands.append_journal_entry import AppendJournalEntryCommandHandler
from grooveloop.journal.application.queries.read_journal_entries import ReadJournalEntriesQueryHandler
from grooveloop.journal.domain.agent_run_context_repository import AgentRunContextRepository
from grooveloop.journal.domain.journal_entry_repository import JournalEntryRepository
from grooveloop.journal.infrastructure.filesystem_journal_entry_repository import (
    FilesystemJournalEntryRepository,
)
from grooveloop.journal.infrastructure.local_agent_run_context_repository import (
    LocalAgentRunContextRepository,
)
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.application.queries.read_journal_entries import ReadJournalEntriesQuery
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.injector_lookup import resolve
from grooveloop.shared.infrastructure.repos_dir import ReposDir
from grooveloop.shared.infrastructure.runs_dir import RunsDir


class JournalModule(Module):
    def configure(self, binder: Binder) -> None:
        query_bus = resolve(binder.injector, QueryBus)
        query_bus.register(ReadJournalEntriesQuery, ReadJournalEntriesQueryHandler)

    @provider
    def journal_entry_repository(self, repos_dir: ReposDir) -> JournalEntryRepository:
        return FilesystemJournalEntryRepository(repos_dir=repos_dir.value)

    @provider
    def agent_run_context_repository(self, runs_dir: RunsDir) -> AgentRunContextRepository:
        return LocalAgentRunContextRepository(runs_dir=runs_dir.value)

    @provider
    def append_journal_entry_command_handler(
        self, journal_entry_repository: JournalEntryRepository, clock: Clock
    ) -> AppendJournalEntryCommandHandler:
        return AppendJournalEntryCommandHandler(journal_entry_repository=journal_entry_repository, clock=clock)

    @provider
    def read_journal_entries_query_handler(
        self, journal_entry_repository: JournalEntryRepository
    ) -> ReadJournalEntriesQueryHandler:
        return ReadJournalEntriesQueryHandler(journal_entry_repository=journal_entry_repository)

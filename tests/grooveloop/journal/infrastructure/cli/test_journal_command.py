from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, create_autospec

import pytest

from grooveloop.bootstrap import container
from grooveloop.journal.application.commands.append_journal_entry import (
    AppendJournalEntryCommand,
    AppendJournalEntryCommandHandler,
)
from grooveloop.journal.application.queries.read_journal_entries import ReadJournalEntriesQueryHandler
from grooveloop.journal.domain.agent_run_context_repository import AgentRunContextRepository
from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.journal.domain.journal_entry_repository import JournalEntryRepository
from grooveloop.journal.infrastructure.cli import journal_command
from grooveloop.journal.infrastructure.filesystem_journal_entry_repository import (
    FilesystemJournalEntryRepository,
)
from grooveloop.journal.infrastructure.local_agent_run_context_repository import (
    LocalAgentRunContextRepository,
)
from grooveloop.shared.application.queries.read_journal_entries import (
    JournalEntryDTO,
    ReadJournalEntriesQuery,
    ReadJournalEntriesQueryResult,
)
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode
from tests.grooveloop.journal.mothers.journal_entry_mother import JournalEntryMother

if TYPE_CHECKING:
    from pathlib import Path

_WRITTEN_AT = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
_RUN_STARTED_AT = datetime(2026, 9, 10, 11, 0, 0, tzinfo=UTC)


def _write_run_metadata(runs_dir: Path, run_id: str, repo: str, story_id: str | None, profile: str | None) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"repo": repo, "story_id": story_id, "profile": profile, "started_at": _RUN_STARTED_AT.isoformat()})
    )


@pytest.fixture
def read_journal_entries_handler() -> Any:
    mock = create_autospec(ReadJournalEntriesQueryHandler, spec_set=True, instance=True)
    with container.override(ReadJournalEntriesQueryHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestJournalCommand:
    def test_should_print_each_entry_and_exit_zero(
        self, read_journal_entries_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        read_journal_entries_handler.return_value = ReadJournalEntriesQueryResult(
            entries=[
                JournalEntryDTO(
                    kind="finding",
                    author="human",
                    body="the fixture does not clean the DB",
                    written_at=_WRITTEN_AT.isoformat(),
                )
            ]
        )

        exit_code = journal_command.run(repo="acme/playground", story=999)

        assert exit_code == 0
        query = read_journal_entries_handler.call_args.args[0]
        assert query == ReadJournalEntriesQuery(repo="acme/playground", story_id="999", kinds=None)
        assert "the fixture does not clean the DB" in capsys.readouterr().out

    def test_should_print_nothing_when_the_story_has_no_entries(
        self, read_journal_entries_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        read_journal_entries_handler.return_value = ReadJournalEntriesQueryResult(entries=[])

        exit_code = journal_command.run(repo="acme/playground", story=1000)

        assert exit_code == 0
        assert capsys.readouterr().out == ""

    def test_should_forward_the_requested_kinds(self, read_journal_entries_handler: Mock) -> None:
        read_journal_entries_handler.return_value = ReadJournalEntriesQueryResult(entries=[])

        journal_command.run(repo="acme/playground", story=999, kinds=["constraint"])

        query = read_journal_entries_handler.call_args.args[0]
        assert query == ReadJournalEntriesQuery(repo="acme/playground", story_id="999", kinds=["constraint"])

    def test_should_exit_with_usage_error_on_stderr_when_a_requested_kind_is_invalid(
        self, read_journal_entries_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        read_journal_entries_handler.side_effect = ValueError("'inventado' is not a valid EntryKind")

        exit_code = journal_command.run(repo="acme/playground", story=999, kinds=["inventado"])

        captured = capsys.readouterr()
        assert exit_code == ExitCode.USAGE_ERROR
        assert captured.out == ""
        assert "invalid entry kind: 'inventado' is not a valid EntryKind" in captured.err

    def test_should_resolve_repo_and_story_from_the_run_pointed_by_the_env_var(
        self, read_journal_entries_handler: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        read_journal_entries_handler.return_value = ReadJournalEntriesQueryResult(entries=[])
        _write_run_metadata(tmp_path, "r-1", repo="acme/playground", story_id="10", profile="developer")
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-1")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = journal_command.run(repo=None, story=None)

        assert exit_code == 0
        query = read_journal_entries_handler.call_args.args[0]
        assert query == ReadJournalEntriesQuery(
            repo="acme/playground", story_id="10", kinds=None, written_after=_RUN_STARTED_AT
        )

    def test_should_say_so_in_one_line_when_the_run_finds_no_new_entries(
        self,
        read_journal_entries_handler: Mock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        read_journal_entries_handler.return_value = ReadJournalEntriesQueryResult(entries=[])
        _write_run_metadata(tmp_path, "r-5", repo="acme/playground", story_id="10", profile="developer")
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-5")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = journal_command.run(repo=None, story=None)

        assert exit_code == 0
        assert capsys.readouterr().out == "no new journal entries since the run started\n"

    def test_should_exit_with_missing_context_on_stderr_when_the_context_is_missing(
        self, read_journal_entries_handler: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("GROOVELOOP_RUN_ID", raising=False)

        exit_code = journal_command.run(repo=None, story=None)

        captured = capsys.readouterr()
        assert exit_code == ExitCode.MISSING_CONTEXT
        assert read_journal_entries_handler.call_count == 0
        assert captured.out == ""
        assert "missing context: pass --repo and --story" in captured.err

    def test_should_not_fall_back_to_the_run_context_when_only_repo_is_given(
        self,
        read_journal_entries_handler: Mock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run_metadata(tmp_path, "r-3", repo="other/repo", story_id="77", profile="developer")
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-3")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = journal_command.run(repo="explicit/repo", story=None)

        assert exit_code == ExitCode.USAGE_ERROR
        assert read_journal_entries_handler.call_count == 0
        assert "--repo and --story must be passed together" in capsys.readouterr().err

    def test_should_not_fall_back_to_the_run_context_when_only_story_is_given(
        self, read_journal_entries_handler: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_run_metadata(tmp_path, "r-4", repo="other/repo", story_id="77", profile="developer")
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-4")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = journal_command.run(repo=None, story=42)

        assert exit_code == ExitCode.USAGE_ERROR
        assert read_journal_entries_handler.call_count == 0

    def test_should_exit_with_missing_context_when_the_env_run_has_no_story_id(
        self, read_journal_entries_handler: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_run_metadata(tmp_path, "r-2", repo="owner/repo", story_id=None, profile=None)
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-2")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = journal_command.run(repo=None, story=None)

        assert exit_code == ExitCode.MISSING_CONTEXT
        assert read_journal_entries_handler.call_count == 0


@pytest.mark.integration
class TestJournalCommandEndToEnd:
    def test_should_read_a_previously_written_entry_through_the_real_wiring(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with container.override(JournalEntryRepository, FilesystemJournalEntryRepository(repos_dir=tmp_path)):
            handler = container.get(AppendJournalEntryCommandHandler)
            handler(
                AppendJournalEntryCommand(
                    repo="acme/playground",
                    story_id="999",
                    kind="finding",
                    author="human",
                    body="the fixture does not clean the DB",
                )
            )

            exit_code = journal_command.run(repo="acme/playground", story=999)

        assert exit_code == 0
        assert "the fixture does not clean the DB" in capsys.readouterr().out

    def test_should_read_only_the_entries_written_after_the_run_started(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        journal_entry_repository = FilesystemJournalEntryRepository(repos_dir=tmp_path / "repos")
        for body, written_at in [
            ("do not touch the legacy client", datetime(2026, 9, 10, 10, 0, 0, tzinfo=UTC)),
            ("use the new client", _WRITTEN_AT),
        ]:
            journal_entry_repository.save(
                JournalEntryMother.create(
                    repo="acme/playground",
                    story_id="10",
                    kind=EntryKind.DIRECTIVE,
                    author="human",
                    body=body,
                    written_at=written_at,
                )
            )
        _write_run_metadata(tmp_path / "runs", "r-6", repo="acme/playground", story_id="10", profile="developer")
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-6")

        with (
            container.override(JournalEntryRepository, journal_entry_repository),
            container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path / "runs")),
        ):
            exit_code = journal_command.run(repo=None, story=None)

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "use the new client" in out
        assert "do not touch the legacy client" not in out

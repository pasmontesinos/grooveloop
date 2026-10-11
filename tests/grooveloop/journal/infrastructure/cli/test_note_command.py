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
from grooveloop.journal.domain.agent_run_context_repository import AgentRunContextRepository
from grooveloop.journal.domain.journal_entry_repository import JournalEntryRepository
from grooveloop.journal.infrastructure.cli import note_command
from grooveloop.journal.infrastructure.filesystem_journal_entry_repository import (
    FilesystemJournalEntryRepository,
)
from grooveloop.journal.infrastructure.local_agent_run_context_repository import (
    LocalAgentRunContextRepository,
)
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def append_journal_entry_handler() -> Any:
    mock = create_autospec(AppendJournalEntryCommandHandler, spec_set=True, instance=True)
    with container.override(AppendJournalEntryCommandHandler, mock):
        yield mock


_RUN_STARTED_AT = datetime(2026, 9, 10, 11, 0, 0, tzinfo=UTC)


def _write_run_metadata(runs_dir: Path, run_id: str, repo: str, story_id: str | None, profile: str | None) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"repo": repo, "story_id": story_id, "profile": profile, "started_at": _RUN_STARTED_AT.isoformat()})
    )


@pytest.mark.entrypoint
class TestNoteCommand:
    def test_should_append_the_entry_and_exit_zero(self, append_journal_entry_handler: Mock) -> None:
        exit_code = note_command.run(
            repo="acme/playground", story=999, kind="finding", body="the fixture does not clean the DB"
        )

        assert exit_code == 0
        command = append_journal_entry_handler.call_args.args[0]
        assert command == AppendJournalEntryCommand(
            repo="acme/playground",
            story_id="999",
            kind="finding",
            author="human",
            body="the fixture does not clean the DB",
        )

    def test_should_exit_with_usage_error_on_stderr_when_the_kind_is_invalid(
        self, append_journal_entry_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        append_journal_entry_handler.side_effect = ValueError("'inventado' is not a valid EntryKind")

        exit_code = note_command.run(repo="acme/playground", story=999, kind="inventado", body="x")

        captured = capsys.readouterr()
        assert exit_code == ExitCode.USAGE_ERROR
        assert captured.out == ""
        assert "invalid entry kind: 'inventado' is not a valid EntryKind" in captured.err

    def test_should_resolve_repo_story_and_author_from_the_run_pointed_by_the_env_var(
        self, append_journal_entry_handler: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_run_metadata(tmp_path, "r-1", repo="acme/playground", story_id="10", profile="developer")
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-1")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = note_command.run(repo=None, story=None, kind="decision", body="identity probe")

        assert exit_code == 0
        command = append_journal_entry_handler.call_args.args[0]
        assert command == AppendJournalEntryCommand(
            repo="acme/playground",
            story_id="10",
            kind="decision",
            author="developer",
            body="identity probe",
        )

    def test_should_exit_with_missing_context_on_stderr_when_the_context_is_missing(
        self, append_journal_entry_handler: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("GROOVELOOP_RUN_ID", raising=False)

        exit_code = note_command.run(repo=None, story=None, kind="decision", body="no context")

        captured = capsys.readouterr()
        assert exit_code == ExitCode.MISSING_CONTEXT
        assert append_journal_entry_handler.call_count == 0
        assert captured.out == ""
        assert "missing context: pass --repo and --story" in captured.err

    def test_should_not_fall_back_to_the_run_context_when_only_repo_is_given(
        self,
        append_journal_entry_handler: Mock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run_metadata(tmp_path, "r-3", repo="other/repo", story_id="77", profile="developer")
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-3")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = note_command.run(repo="explicit/repo", story=None, kind="decision", body="b")

        assert exit_code == ExitCode.USAGE_ERROR
        assert append_journal_entry_handler.call_count == 0
        assert "--repo and --story must be passed together" in capsys.readouterr().err

    def test_should_not_fall_back_to_the_run_context_when_only_story_is_given(
        self, append_journal_entry_handler: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_run_metadata(tmp_path, "r-4", repo="other/repo", story_id="77", profile="developer")
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-4")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = note_command.run(repo=None, story=42, kind="decision", body="b")

        assert exit_code == ExitCode.USAGE_ERROR
        assert append_journal_entry_handler.call_count == 0

    def test_should_exit_with_missing_context_when_the_env_run_has_no_story_id(
        self, append_journal_entry_handler: Mock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_run_metadata(tmp_path, "r-2", repo="owner/repo", story_id=None, profile=None)
        monkeypatch.setenv("GROOVELOOP_RUN_ID", "r-2")

        with container.override(AgentRunContextRepository, LocalAgentRunContextRepository(runs_dir=tmp_path)):
            exit_code = note_command.run(repo=None, story=None, kind="decision", body="no story")

        assert exit_code == ExitCode.MISSING_CONTEXT
        assert append_journal_entry_handler.call_count == 0


@pytest.mark.integration
class TestNoteCommandEndToEnd:
    def test_should_write_the_entry_through_the_real_wiring(self, tmp_path: Path) -> None:
        with container.override(JournalEntryRepository, FilesystemJournalEntryRepository(repos_dir=tmp_path)):
            exit_code = note_command.run(
                repo="acme/playground", story=999, kind="finding", body="the fixture does not clean the DB"
            )

        assert exit_code == 0
        journal_dir = tmp_path / "acme" / "playground" / "stories" / "999" / "journal"
        files = list(journal_dir.iterdir())
        assert len(files) == 1
        stored = json.loads(files[0].read_text())
        assert stored["kind"] == "finding"
        assert stored["body"] == "the fixture does not clean the DB"

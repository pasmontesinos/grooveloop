from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.infrastructure.claude_log_reader import ClaudeLogReader
from grooveloop.shared.infrastructure.filesystem_agent_run_logs import FilesystemAgentRunLogs
from grooveloop.shared.infrastructure.opencode_log_reader import OpencodeLogReader

if TYPE_CHECKING:
    from pathlib import Path

_RUN_ID = "5cf547af-7d1e-4f1b-9d4e-3a0c1b2d4e5f"


def _claude_tool_use(tool_use_id: str, command: str) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "id": tool_use_id, "name": "Bash", "input": {"command": command}}]
            },
        }
    )


def _opencode_tool_use(command: str) -> str:
    return json.dumps(
        {"type": "tool_use", "part": {"id": "prt_1", "tool": "bash", "state": {"input": {"command": command}}}}
    )


def _run_dir(tmp_path: Path, log: str | None, engine: str | None = "claude") -> Path:
    run_dir = tmp_path / _RUN_ID
    run_dir.mkdir()
    metadata = {"repo": "acme/tooling", "slice_id": "488"}
    if engine is not None:
        metadata["engine"] = engine
    (run_dir / "run.json").write_text(json.dumps(metadata))
    if log is not None:
        (run_dir / "agent.log").write_text(log)

    return run_dir


def _logs(tmp_path: Path) -> FilesystemAgentRunLogs:
    return FilesystemAgentRunLogs(
        runs_dir=tmp_path, log_readers={reader.engine: reader for reader in [ClaudeLogReader(), OpencodeLogReader()]}
    )


@pytest.mark.integration
class TestFilesystemAgentRunLogs:
    def test_should_read_the_actions_of_the_log_with_the_reader_of_its_engine(self, tmp_path: Path) -> None:
        _run_dir(tmp_path, f"{_opencode_tool_use('make test')}\n", engine="opencode")

        chunk = _logs(tmp_path).read(_RUN_ID, 0)

        assert chunk is not None
        assert [action.description for action in chunk.actions] == ["bash · make test"]

    def test_should_read_a_run_without_engine_as_a_claude_run(self, tmp_path: Path) -> None:
        _run_dir(tmp_path, f"{_claude_tool_use('toolu_1', 'make test')}\n", engine=None)

        chunk = _logs(tmp_path).read(_RUN_ID, 0)

        assert chunk is not None
        assert [action.tool_use_id for action in chunk.actions] == ["toolu_1"]

    def test_should_read_only_the_actions_written_after_the_offset(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, f"{_claude_tool_use('toolu_1', 'make test')}\n")
        logs = _logs(tmp_path)
        first = logs.read(_RUN_ID, 0)
        assert first is not None
        with (run_dir / "agent.log").open("a") as log:
            log.write(f"{_claude_tool_use('toolu_2', 'make check-types')}\n")

        second = logs.read(_RUN_ID, first.offset)

        assert second is not None
        assert [action.description for action in second.actions] == ["Bash · make check-types"]
        assert second.offset == (run_dir / "agent.log").stat().st_size

    def test_should_leave_a_line_still_being_written_for_the_next_read(self, tmp_path: Path) -> None:
        complete = f"{_claude_tool_use('toolu_1', 'make test')}\n"
        _run_dir(tmp_path, complete + _claude_tool_use("toolu_2", "make check-types")[:20])

        chunk = _logs(tmp_path).read(_RUN_ID, 0)

        assert chunk is not None
        assert [action.tool_use_id for action in chunk.actions] == ["toolu_1"]
        assert chunk.offset == len(complete.encode())

    def test_should_read_nothing_when_the_run_has_no_log(self, tmp_path: Path) -> None:
        _run_dir(tmp_path, None)

        assert _logs(tmp_path).read(_RUN_ID, 0) is None

    def test_should_read_nothing_when_the_run_does_not_exist(self, tmp_path: Path) -> None:
        assert _logs(tmp_path).read(_RUN_ID, 0) is None

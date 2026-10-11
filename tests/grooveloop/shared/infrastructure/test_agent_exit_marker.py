from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.infrastructure.agent_exit_marker import (
    exit_marker_command,
    is_exit_marker,
    read_exit_code,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestExitMarkerCommand:
    def test_prints_the_marker_with_the_exit_status_of_the_engine(self) -> None:
        assert exit_marker_command() == 'printf "\\n[AGENT_EXIT] %s\\n" "$?"'


class TestIsExitMarker:
    def test_recognises_the_line_written_by_the_wrapper(self) -> None:
        assert is_exit_marker("[AGENT_EXIT] 0") is True

    def test_rejects_a_line_from_the_engine(self) -> None:
        assert is_exit_marker('{"type": "result"}') is False


@pytest.mark.integration
class TestReadExitCode:
    def test_reads_the_status_of_a_run_that_succeeded(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("done\n[AGENT_EXIT] 0\n")

        assert read_exit_code(log) == 0

    def test_reads_the_status_of_a_run_that_failed(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("boom\n[AGENT_EXIT] 1\n")

        assert read_exit_code(log) == 1

    def test_returns_nothing_while_the_run_is_still_going(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("working\n")

        assert read_exit_code(log) is None

    def test_only_looks_at_the_tail_of_the_log(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        trailing_noise = "".join(f"noise-{index}\n" for index in range(100))
        log.write_text(f"[AGENT_EXIT] 0\n{trailing_noise}")

        assert read_exit_code(log) is None

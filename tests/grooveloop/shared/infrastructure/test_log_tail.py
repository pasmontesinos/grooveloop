from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.infrastructure.log_tail import read_log_tail

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestReadLogTail:
    def test_returns_the_last_complete_lines_of_the_file(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("first\nsecond\nthird\n[AGENT_EXIT] 0\n")

        assert read_log_tail(log, lines=2) == ["third", "[AGENT_EXIT] 0"]

    def test_returns_every_line_when_the_file_is_shorter_than_the_requested_lines(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("only\n")

        assert read_log_tail(log, lines=5) == ["only"]

    def test_returns_nothing_for_an_empty_file(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("")

        assert read_log_tail(log, lines=5) == []

    def test_returns_the_last_line_when_the_file_has_no_trailing_newline(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("first\n[AGENT_EXIT] 1")

        assert read_log_tail(log, lines=1) == ["[AGENT_EXIT] 1"]

    def test_returns_complete_lines_longer_than_the_read_block(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        long_line = "x" * 40_000
        log.write_text(f"first\n{long_line}\n[AGENT_EXIT] 0\n")

        assert read_log_tail(log, lines=2) == [long_line, "[AGENT_EXIT] 0"]

    def test_never_returns_lines_beyond_the_byte_cap(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("".join(f"line-{index}\n" for index in range(10, 100)))

        assert read_log_tail(log, lines=50, max_bytes=30) == ["line-97", "line-98", "line-99"]

    def test_drops_the_partial_line_cut_by_the_byte_cap(self, tmp_path: Path) -> None:
        log = tmp_path / "agent.log"
        log.write_text("aaaaaaaaaa\nbbbb\n")

        assert read_log_tail(log, lines=5, max_bytes=8) == ["bbbb"]

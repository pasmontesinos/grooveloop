from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.infrastructure.log_tail import read_log_tail

if TYPE_CHECKING:
    from pathlib import Path

_EXIT_MARKER = "[AGENT_EXIT]"
_VANISHED_MARKER = "[AGENT_VANISHED]"
_STALLED_MARKER = "[AGENT_STALLED]"
_TAIL_LINES = 5
_TERMINATED_EXIT_CODE = 143


def exit_marker_command() -> str:
    return f'printf "\\n{_EXIT_MARKER} %s\\n" "$?"'


def is_exit_marker(line: str) -> bool:
    return line.startswith(_EXIT_MARKER)


def read_exit_code(log: Path) -> int | None:
    for line in reversed(read_log_tail(log, _TAIL_LINES)):
        if is_exit_marker(line):
            return int(line.removeprefix(_EXIT_MARKER).strip())

    return None


def is_terminated(exit_code: int) -> bool:
    return exit_code == _TERMINATED_EXIT_CODE


def vanished_exit_lines() -> str:
    return f"\n{_VANISHED_MARKER}\n{_EXIT_MARKER} {_TERMINATED_EXIT_CODE}\n"


def is_vanished(log: Path) -> bool:
    return _VANISHED_MARKER in read_log_tail(log, _TAIL_LINES)


def stalled_exit_lines() -> str:
    return f"\n{_STALLED_MARKER}\n{_EXIT_MARKER} {_TERMINATED_EXIT_CODE}\n"


def is_stalled(log: Path) -> bool:
    return _STALLED_MARKER in read_log_tail(log, _TAIL_LINES)

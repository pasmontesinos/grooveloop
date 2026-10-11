from __future__ import annotations

import re
from dataclasses import dataclass
from textwrap import dedent
from typing import Self

_HEADING = re.compile(
    r"^(?P<indent>[ \t]*)(?P<bullet>[-*+][ \t]+)?(?:#{1,6}[ \t]+)?\*{0,2}[ \t]*"
    r"observable[ \t]+verification[ \t]*[:*]*[ \t]*",
    re.IGNORECASE,
)
_NEXT_HEADING = re.compile(r"^#{1,6} ")


@dataclass(frozen=True)
class VerificationSection:
    text: str

    @classmethod
    def parse(cls, body: str) -> Self | None:
        lines = body.splitlines()
        heading = _find_heading(lines)
        if heading is None:
            return None

        start, match = heading
        block = _block_from(lines, start, match)
        if block.strip() == "":
            return None

        return cls(text=block.strip())


def _find_heading(lines: list[str]) -> tuple[int, re.Match[str]] | None:
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match is not None:
            return index, match

    return None


def _block_from(lines: list[str], start: int, heading: re.Match[str]) -> str:
    indent = len(heading.group("indent"))
    under_a_bullet = heading.group("bullet") is not None
    rest: list[str] = []

    for line in lines[start + 1 :]:
        if _stops_the_block(line, indent, under_a_bullet):
            break
        rest.append(line)

    return "\n".join([lines[start][heading.end() :], dedent("\n".join(rest))])


def _stops_the_block(line: str, indent: int, under_a_bullet: bool) -> bool:
    if _NEXT_HEADING.match(line):
        return True

    if not under_a_bullet or line.strip() == "":
        return False

    return len(line) - len(line.lstrip()) <= indent

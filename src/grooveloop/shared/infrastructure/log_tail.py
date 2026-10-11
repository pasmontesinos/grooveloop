from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

MAX_TAIL_BYTES = 65_536
_BLOCK_SIZE = 8_192


def read_log_tail(path: Path, lines: int, max_bytes: int = MAX_TAIL_BYTES) -> list[str]:
    tail, reached_start = _read_tail_bytes(path, lines, max_bytes)
    if not reached_start:
        tail = _drop_partial_first_line(tail)

    return tail.decode("utf-8", errors="replace").splitlines()[-lines:]


def _read_tail_bytes(path: Path, lines: int, max_bytes: int) -> tuple[bytes, bool]:
    with path.open("rb") as stream:
        size = stream.seek(0, os.SEEK_END)
        limit = min(size, max_bytes)
        tail = b""
        while len(tail) < limit and tail.count(b"\n") <= lines:
            block = min(_BLOCK_SIZE, limit - len(tail))
            stream.seek(size - len(tail) - block)
            tail = stream.read(block) + tail

        return tail, len(tail) == size


def _drop_partial_first_line(tail: bytes) -> bytes:
    newline = tail.find(b"\n")

    return tail[newline + 1 :] if newline >= 0 else b""

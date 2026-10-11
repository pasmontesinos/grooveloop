from __future__ import annotations

_MINUTE = 60


def format_elapsed(seconds: float | None) -> str:
    total = int(seconds or 0)
    if total < _MINUTE:
        return f"{total}s"

    return f"{total // _MINUTE}m{total % _MINUTE:02d}s"

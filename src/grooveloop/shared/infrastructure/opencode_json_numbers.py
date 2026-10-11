from __future__ import annotations

from typing import Any


def parse_int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def parse_float(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0

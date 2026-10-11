from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutoMerge:
    value: bool

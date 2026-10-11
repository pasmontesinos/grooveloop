from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PullRequestFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None

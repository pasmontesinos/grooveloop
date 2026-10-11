from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    pid: int

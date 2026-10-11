from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.loop_run import LoopRun


@dataclass(frozen=True)
class LoopActivity:
    running: int
    elapsed_seconds: float
    cost_usd: float


def activity_of(runs: list[LoopRun]) -> LoopActivity | None:
    live = [run for run in runs if run.running]
    if len(live) == 0:
        return None

    return LoopActivity(
        running=len(live),
        elapsed_seconds=max(run.elapsed_seconds for run in live),
        cost_usd=sum(run.cost_usd for run in runs),
    )

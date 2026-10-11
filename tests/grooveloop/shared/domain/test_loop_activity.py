from __future__ import annotations

import pytest

from grooveloop.shared.domain.loop_activity import activity_of
from grooveloop.shared.domain.loop_run import LoopRun


def _run(
    slice_number: str = "1",
    running: bool = True,
    elapsed_seconds: float = 60.0,
    cost_usd: float = 0.0,
    silent_seconds: float = 0.0,
) -> LoopRun:
    return LoopRun(
        slice_number=slice_number,
        running=running,
        elapsed_seconds=elapsed_seconds,
        cost_usd=cost_usd,
        silent_seconds=silent_seconds,
    )


class TestActivityOf:
    def test_should_report_no_activity_without_runs(self) -> None:
        assert activity_of([]) is None

    def test_should_report_no_activity_when_every_run_has_finished(self) -> None:
        assert activity_of([_run(running=False, cost_usd=0.8)]) is None

    def test_should_count_only_the_runs_that_are_still_going(self) -> None:
        activity = activity_of([_run(slice_number="1"), _run(slice_number="2"), _run(slice_number="3", running=False)])

        assert activity is not None
        assert activity.running == 2

    def test_should_take_the_time_of_the_oldest_live_run(self) -> None:
        activity = activity_of([_run(elapsed_seconds=30.0), _run(elapsed_seconds=240.0)])

        assert activity is not None
        assert activity.elapsed_seconds == 240.0

    def test_should_add_up_the_cost_of_every_run_of_the_repo(self) -> None:
        activity = activity_of(
            [_run(cost_usd=0.0), _run(running=False, cost_usd=0.5), _run(running=False, cost_usd=0.32)]
        )

        assert activity is not None
        assert activity.cost_usd == pytest.approx(0.82)

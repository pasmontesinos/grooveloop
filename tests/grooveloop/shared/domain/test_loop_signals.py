from __future__ import annotations

from datetime import UTC, datetime

from grooveloop.shared.domain.loop_run import LoopRun
from grooveloop.shared.domain.loop_signal_category import LoopSignalCategory
from grooveloop.shared.domain.loop_signal_kind import LoopSignalKind
from grooveloop.shared.domain.loop_signals import LoopSignal, signals_of
from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus
from grooveloop.shared.domain.snapshot_tick import SnapshotTick
from grooveloop.shared.domain.tick_outcome import TickOutcome

_NOW = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)


def _snapshot() -> LoopSnapshot:
    return LoopSnapshot(
        repo="owner/repo",
        tick=SnapshotTick(outcome=TickOutcome.OK, at=_NOW, duration_seconds=38, interval_seconds=600),
        stories=[],
    )


def _story_with_slices(*slices: SnapshotSlice) -> SnapshotStory:
    return SnapshotStory(
        number="361", status=SnapshotStoryStatus.IN_PROGRESS, title="a story", slices=list(slices), lessons=[]
    )


def _slice(number: str, status: str, pr_number: str | None = None) -> SnapshotSlice:
    return SnapshotSlice(number=number, status=SnapshotSliceStatus(status), title="a slice", pr_number=pr_number)


def _snapshot_with(*stories: SnapshotStory) -> LoopSnapshot:
    return LoopSnapshot(
        repo="owner/repo",
        tick=SnapshotTick(outcome=TickOutcome.OK, at=_NOW, duration_seconds=38, interval_seconds=600),
        stories=list(stories),
    )


def _run(slice_number: str, running: bool, silent_seconds: float) -> LoopRun:
    return LoopRun(
        slice_number=slice_number,
        running=running,
        elapsed_seconds=600.0,
        cost_usd=0.0,
        silent_seconds=silent_seconds,
    )


class TestSignalsOf:
    def test_should_break_on_a_run_that_has_gone_quiet(self) -> None:
        signals = signals_of(_snapshot(), 10, [_run("351", running=True, silent_seconds=400.0)], 300)

        assert signals == [
            LoopSignal(kind=LoopSignalKind.SILENT_AGENT, category=LoopSignalCategory.BROKEN, reference="351")
        ]

    def test_should_stay_quiet_while_the_run_keeps_talking(self) -> None:
        assert signals_of(_snapshot(), 10, [_run("351", running=True, silent_seconds=120.0)], 300) == []

    def test_should_ignore_the_silence_of_a_run_that_already_finished(self) -> None:
        assert signals_of(_snapshot(), 10, [_run("351", running=False, silent_seconds=9000.0)], 300) == []

    def test_should_wait_on_a_blocked_slice_with_its_own_number(self) -> None:
        snapshot = _snapshot_with(_story_with_slices(_slice("371", "blocked")))

        assert signals_of(snapshot, 10, [], 300) == [
            LoopSignal(kind=LoopSignalKind.BLOCKED_SLICE, category=LoopSignalCategory.WAITING, reference="371")
        ]

    def test_should_put_the_blocked_slice_ahead_of_the_pull_request_that_waits(self) -> None:
        snapshot = _snapshot_with(
            _story_with_slices(_slice("370", "pr_open", pr_number="376"), _slice("371", "blocked"))
        )

        kinds = [signal.kind for signal in signals_of(snapshot, 10, [], 300)]

        assert kinds == [LoopSignalKind.BLOCKED_SLICE, LoopSignalKind.PULL_REQUEST_WAITING]

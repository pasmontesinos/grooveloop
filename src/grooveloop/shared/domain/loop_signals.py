from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.domain.learning_gate import learning_gate
from grooveloop.shared.domain.loop_signal_category import LoopSignalCategory
from grooveloop.shared.domain.loop_signal_kind import LoopSignalKind
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.tick_outcome import TickOutcome

if TYPE_CHECKING:
    from grooveloop.shared.domain.loop_run import LoopRun
    from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
    from grooveloop.shared.domain.snapshot_story import SnapshotStory

_TICKS_BEFORE_STALE = 2


@dataclass(frozen=True)
class LoopSignal:
    kind: LoopSignalKind
    category: LoopSignalCategory
    reference: str | None = None


def signals_of(
    snapshot: LoopSnapshot,
    tick_age_seconds: int,
    runs: list[LoopRun],
    stall_after_seconds: int,
) -> list[LoopSignal]:
    return _broken_signals(snapshot, tick_age_seconds, runs, stall_after_seconds) + _waiting_signals(snapshot)


def _broken_signals(
    snapshot: LoopSnapshot,
    tick_age_seconds: int,
    runs: list[LoopRun],
    stall_after_seconds: int,
) -> list[LoopSignal]:
    signal_list = []
    if snapshot.tick.outcome == TickOutcome.FAILED:
        signal_list.append(_broken(LoopSignalKind.FAILED_TICK))

    if tick_age_seconds > _TICKS_BEFORE_STALE * snapshot.tick.interval_seconds:
        signal_list.append(_broken(LoopSignalKind.STALE_SNAPSHOT))

    signal_list.extend(
        _broken(LoopSignalKind.SILENT_AGENT, run.slice_number)
        for run in runs
        if run.running and run.silent_seconds >= stall_after_seconds
    )
    signal_list.extend(
        _broken(LoopSignalKind.FAILED_SLICE, a_slice.number)
        for story in snapshot.stories
        for a_slice in story.slices
        if a_slice.status is SnapshotSliceStatus.FAILED
    )

    return signal_list


def _waiting_signals(snapshot: LoopSnapshot) -> list[LoopSignal]:
    signal_list = [
        _waiting(LoopSignalKind.BLOCKED_SLICE, a_slice.number)
        for story in snapshot.stories
        for a_slice in story.slices
        if a_slice.status is SnapshotSliceStatus.BLOCKED
    ]
    signal_list.extend(
        _waiting(LoopSignalKind.PULL_REQUEST_WAITING, a_slice.pr_number)
        for story in snapshot.stories
        for a_slice in story.slices
        if a_slice.status is SnapshotSliceStatus.PR_OPEN and a_slice.pr_number is not None
    )
    signal_list.extend(
        _waiting(LoopSignalKind.BLOCKING_LESSON, blocked)
        for blocked in (_blocked_slice_of(story) for story in snapshot.stories)
        if blocked is not None
    )

    return signal_list


def _blocked_slice_of(story: SnapshotStory) -> str | None:
    pending = {lesson.source_pull_request_number for lesson in story.lessons if not lesson.resolved}
    gate = learning_gate(story.slices, pending)
    if gate is None:
        return None

    return story.slices[gate[0] - 1].number


def _broken(kind: LoopSignalKind, reference: str | None = None) -> LoopSignal:
    return LoopSignal(kind=kind, category=LoopSignalCategory.BROKEN, reference=reference)


def _waiting(kind: LoopSignalKind, reference: str | None = None) -> LoopSignal:
    return LoopSignal(kind=kind, category=LoopSignalCategory.WAITING, reference=reference)

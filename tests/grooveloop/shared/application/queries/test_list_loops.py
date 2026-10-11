from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from grooveloop.shared.application.queries.list_loops import (
    ActivityDTO,
    ListLoopsQuery,
    ListLoopsQueryHandler,
    LoopDTO,
    SignalDTO,
    TickDTO,
)
from grooveloop.shared.application.queries.list_repo_sessions import (
    AgentSessionDTO,
    ListRepoSessionsQuery,
    ListRepoSessionsQueryResult,
)
from grooveloop.shared.domain.loop_heartbeat import LoopHeartbeat
from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
from grooveloop.shared.domain.snapshot_lesson import SnapshotLesson
from grooveloop.shared.domain.snapshot_lesson_status import SnapshotLessonStatus
from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus
from grooveloop.shared.domain.snapshot_tick import SnapshotTick
from grooveloop.shared.domain.tick_outcome import TickOutcome
from tests.playground.shared.infrastructure.clock import clock_at
from tests.playground.shared.infrastructure.fake_loop_presence import FakeLoopPresence
from tests.playground.shared.infrastructure.fake_loop_snapshots import FakeLoopSnapshots
from tests.playground.shared.infrastructure.fake_process_liveness import FakeProcessLiveness
from tests.playground.shared.infrastructure.fake_query_bus import FakeQueryBus

if TYPE_CHECKING:
    from grooveloop.shared.application.queries.query_bus import QueryBus

    pass

_NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
_STALL_AFTER = 300


def _heartbeat(repo: str, pid: int = 100, seconds_ago: float = 0) -> LoopHeartbeat:
    return LoopHeartbeat(repo=repo, pid=pid, at=_NOW - timedelta(seconds=seconds_ago))


def _snapshot(
    repo: str,
    outcome: TickOutcome,
    seconds_ago: float,
    duration_seconds: int,
    interval_seconds: int = 600,
) -> LoopSnapshot:
    return LoopSnapshot(
        repo=repo,
        tick=SnapshotTick(
            outcome=outcome,
            at=_NOW - timedelta(seconds=seconds_ago),
            duration_seconds=duration_seconds,
            interval_seconds=interval_seconds,
        ),
        stories=[],
    )


def _a_slice(number: str, status: str, pr_number: str | None) -> SnapshotSlice:
    return SnapshotSlice(
        number=number, status=SnapshotSliceStatus(status), title=f"slice {number}", pr_number=pr_number
    )


def _lesson(source_pull_request_number: int, resolved: bool) -> SnapshotLesson:
    return SnapshotLesson(
        number="91",
        source_pull_request_number=source_pull_request_number,
        status=SnapshotLessonStatus.IN_PROGRESS,
        conventions_pull_request_number=None,
        resolved=resolved,
    )


def _snapshot_with_slices(
    repo: str,
    slices: list[SnapshotSlice],
    lessons: list[SnapshotLesson] | None = None,
    outcome: TickOutcome = TickOutcome.OK,
) -> LoopSnapshot:
    return LoopSnapshot(
        repo=repo,
        tick=SnapshotTick(outcome=outcome, at=_NOW, duration_seconds=38, interval_seconds=600),
        stories=[
            SnapshotStory(
                number="338",
                status=SnapshotStoryStatus.SLICED,
                title="Panel multirepo",
                slices=slices,
                lessons=lessons or [],
            )
        ],
    )


def _query_bus(sessions: dict[str, list[AgentSessionDTO]]) -> FakeQueryBus:
    return FakeQueryBus(
        {ListRepoSessionsQuery: lambda query: ListRepoSessionsQueryResult(sessions=sessions.get(query.repo, []))}
    )


def _session(
    slice_number: str,
    outcome: str = "running",
    elapsed_seconds: float = 240.0,
    total_cost_usd: float | None = None,
    last_event_at: datetime | None = None,
    started_at: datetime = _NOW,
    has_log: bool = True,
) -> AgentSessionDTO:
    return AgentSessionDTO(
        slice_number=slice_number,
        outcome=outcome,
        task_type="implement_slice",
        engine="claude",
        run_id="run-1",
        started_at=started_at,
        has_log=has_log,
        elapsed_seconds=elapsed_seconds,
        total_cost_usd=total_cost_usd,
        models=[],
        last_event_at=last_event_at,
    )


def _handler(
    heartbeats: list[LoopHeartbeat],
    alive_pids: list[int],
    snapshots: list[LoopSnapshot] | None = None,
    query_bus: QueryBus | None = None,
) -> ListLoopsQueryHandler:
    return ListLoopsQueryHandler(
        loop_presence=FakeLoopPresence(heartbeats),
        process_liveness=FakeProcessLiveness(alive_pids),
        loop_snapshots=FakeLoopSnapshots(snapshots),
        clock=clock_at(_NOW),
        query_bus=query_bus or _query_bus({}),
    )


class TestListLoopsQueryHandler:
    def test_should_report_a_fresh_heartbeat_of_a_running_pid_as_alive(self) -> None:
        handler = _handler([_heartbeat("acme/tooling", pid=100, seconds_ago=3)], alive_pids=[100])

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops == [LoopDTO(repo="acme/tooling", alive=True, age_seconds=3)]

    def test_should_report_a_heartbeat_of_a_gone_pid_as_not_alive(self) -> None:
        handler = _handler([_heartbeat("acme/tooling", pid=100, seconds_ago=3)], alive_pids=[])

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops == [LoopDTO(repo="acme/tooling", alive=False, age_seconds=3)]

    def test_should_report_a_stale_heartbeat_as_not_alive_even_when_the_pid_answers(self) -> None:
        handler = _handler([_heartbeat("acme/tooling", pid=100, seconds_ago=600)], alive_pids=[100])

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops == [LoopDTO(repo="acme/tooling", alive=False, age_seconds=600)]

    def test_should_drop_a_heartbeat_older_than_twelve_hours(self) -> None:
        handler = _handler(
            [
                _heartbeat("acme/shop", pid=100, seconds_ago=13 * 3600),
                _heartbeat("acme/tooling", pid=101, seconds_ago=11 * 3600),
            ],
            alive_pids=[],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert [loop.repo for loop in result.loops] == ["acme/tooling"]

    def test_should_sort_the_loops_alphabetically(self) -> None:
        handler = _handler(
            [
                _heartbeat("acme/tooling", pid=100),
                _heartbeat("acme/shop", pid=101),
                _heartbeat("acme/catalog", pid=102),
            ],
            alive_pids=[100, 101, 102],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert [loop.repo for loop in result.loops] == [
            "acme/catalog",
            "acme/shop",
            "acme/tooling",
        ]

    def test_should_return_no_loop_when_there_is_no_heartbeat(self) -> None:
        handler = _handler([], alive_pids=[])

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops == []

    def test_should_report_the_verdict_of_the_last_tick_of_the_repo(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot("acme/tooling", outcome=TickOutcome.OK, seconds_ago=60, duration_seconds=38)],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].tick == TickDTO(outcome="ok", age_seconds=60, duration_seconds=38)

    def test_should_report_a_failed_tick_with_its_own_outcome(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot("acme/tooling", outcome=TickOutcome.FAILED, seconds_ago=120, duration_seconds=41)],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].tick == TickDTO(outcome="failed", age_seconds=120, duration_seconds=41)

    def test_should_report_no_tick_when_the_repo_has_no_snapshot(self) -> None:
        handler = _handler([_heartbeat("acme/tooling", pid=100, seconds_ago=3)], alive_pids=[100])

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].tick is None

    def test_should_match_every_snapshot_to_its_own_repo(self) -> None:
        handler = _handler(
            [
                _heartbeat("acme/shop", pid=101, seconds_ago=2),
                _heartbeat("acme/tooling", pid=100, seconds_ago=3),
            ],
            alive_pids=[100, 101],
            snapshots=[_snapshot("acme/tooling", outcome=TickOutcome.OK, seconds_ago=60, duration_seconds=38)],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert [loop.tick for loop in result.loops] == [
            None,
            TickDTO(outcome="ok", age_seconds=60, duration_seconds=38),
        ]

    def test_should_signal_a_pull_request_that_waits_for_review(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/tooling", [_a_slice("351", "pr_open", "342")])],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].signals == [SignalDTO(kind="pull_request_waiting", category="waiting", reference="342")]

    def test_should_signal_a_slice_that_failed(self) -> None:
        handler = _handler(
            [_heartbeat("acme/shop", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/shop", [_a_slice("88", "failed", None)])],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].signals == [SignalDTO(kind="failed_slice", category="broken", reference="88")]

    def test_should_signal_a_failed_tick(self) -> None:
        handler = _handler(
            [_heartbeat("acme/shop", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot("acme/shop", outcome=TickOutcome.FAILED, seconds_ago=120, duration_seconds=41)],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].signals == [SignalDTO(kind="failed_tick", category="broken")]

    def test_should_signal_a_snapshot_that_missed_two_ticks(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot("acme/tooling", outcome=TickOutcome.OK, seconds_ago=1500, duration_seconds=38)],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].signals == [SignalDTO(kind="stale_snapshot", category="broken")]

    def test_should_report_no_stale_signal_when_the_tick_interval_covers_the_age(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[
                _snapshot(
                    "acme/tooling",
                    outcome=TickOutcome.OK,
                    seconds_ago=1500,
                    duration_seconds=38,
                    interval_seconds=1800,
                )
            ],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].signals == []

    def test_should_signal_the_slice_that_a_pending_lesson_blocks(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[
                _snapshot_with_slices(
                    "acme/tooling",
                    [_a_slice("350", "merged", "342"), _a_slice("351", "pending", None)],
                    lessons=[_lesson(source_pull_request_number=342, resolved=False)],
                )
            ],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].signals == [SignalDTO(kind="blocking_lesson", category="waiting", reference="351")]

    def test_should_report_no_signal_for_a_healthy_repo(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/tooling", [_a_slice("350", "merged", "342")])],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].signals == []

    def test_should_report_no_signal_when_the_repo_has_no_snapshot(self) -> None:
        handler = _handler([_heartbeat("acme/tooling", pid=100, seconds_ago=3)], alive_pids=[100])

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert result.loops[0].signals == []

    def test_should_put_the_broken_signals_before_the_waiting_ones(self) -> None:
        handler = _handler(
            [_heartbeat("acme/shop", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[
                _snapshot_with_slices(
                    "acme/shop",
                    [_a_slice("351", "pr_open", "342"), _a_slice("88", "failed", None)],
                    outcome=TickOutcome.FAILED,
                )
            ],
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert [signal.kind for signal in result.loops[0].signals] == [
            "failed_tick",
            "failed_slice",
            "pull_request_waiting",
        ]

    def test_should_report_the_activity_of_the_running_agents(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[
                _snapshot_with_slices(
                    "acme/tooling",
                    [_a_slice("350", "merged", None), _a_slice("351", "dispatched", None)],
                )
            ],
            query_bus=_query_bus(
                {
                    "acme/tooling": [
                        _session("351", outcome="running", elapsed_seconds=240.0),
                        _session("350", outcome="succeeded", elapsed_seconds=60.0, total_cost_usd=0.82),
                    ]
                }
            ),
        )

        activity = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER)).loops[0].activity

        assert activity == ActivityDTO(running=1, elapsed_seconds=240.0, cost_usd=0.82)

    def test_should_report_no_activity_when_no_agent_is_running(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/tooling", [_a_slice("350", "merged", None)])],
            query_bus=_query_bus({"acme/tooling": [_session("350", outcome="succeeded")]}),
        )

        assert handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER)).loops[0].activity is None

    def test_should_leave_an_unstarted_run_out_of_the_activity(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/tooling", [_a_slice("351", "dispatched", None)])],
            query_bus=_query_bus(
                {
                    "acme/tooling": [
                        _session("351", elapsed_seconds=240.0),
                        _session("351", has_log=False, started_at=_NOW - timedelta(minutes=6)),
                    ]
                }
            ),
        )

        activity = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER)).loops[0].activity

        assert activity == ActivityDTO(running=1, elapsed_seconds=240.0, cost_usd=0.0)

    def test_should_break_on_a_run_that_stayed_silent_longer_than_the_threshold(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/tooling", [_a_slice("351", "dispatched", None)])],
            query_bus=_query_bus({"acme/tooling": [_session("351", last_event_at=_NOW - timedelta(seconds=400))]}),
        )

        signals = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER)).loops[0].signals

        assert SignalDTO(kind="silent_agent", category="broken", reference="351") in signals

    def test_should_stay_quiet_about_a_run_that_keeps_talking(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/tooling", [_a_slice("351", "dispatched", None)])],
            query_bus=_query_bus({"acme/tooling": [_session("351", last_event_at=_NOW - timedelta(seconds=30))]}),
        )

        assert handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER)).loops[0].signals == []

    def test_should_hand_the_sessions_of_the_open_stories_to_its_caller(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/tooling", [_a_slice("351", "dispatched", None)])],
            query_bus=_query_bus({"acme/tooling": [_session("351")]}),
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert [session.slice_number for session in result.loops[0].sessions] == ["351"]

    def test_should_not_poll_the_runs_of_a_loop_whose_pid_is_gone(self) -> None:
        bus = _query_bus({})
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[],
            query_bus=bus,
        )

        handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert bus.asked == []

    def test_should_ignore_the_sessions_of_a_slice_the_snapshot_no_longer_carries(self) -> None:
        handler = _handler(
            [_heartbeat("acme/tooling", pid=100, seconds_ago=3)],
            alive_pids=[100],
            snapshots=[_snapshot_with_slices("acme/tooling", [_a_slice("351", "pr_open", "342")])],
            query_bus=_query_bus(
                {
                    "acme/tooling": [
                        _session("351", outcome="succeeded", total_cost_usd=0.5),
                        _session("120", outcome="succeeded", total_cost_usd=99.0),
                    ]
                }
            ),
        )

        result = handler(ListLoopsQuery(stall_after_seconds=_STALL_AFTER))

        assert [session.slice_number for session in result.loops[0].sessions] == ["351"]

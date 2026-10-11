from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from grooveloop.shared.application.queries.list_repo_sessions import ListRepoSessionsQuery
from grooveloop.shared.application.queries.query import Query
from grooveloop.shared.application.queries.query_handler import QueryHandler
from grooveloop.shared.application.queries.query_result import QueryResult
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.loop_activity import activity_of
from grooveloop.shared.domain.loop_run import LoopRun
from grooveloop.shared.domain.loop_signals import signals_of
from grooveloop.shared.domain.unstarted_run import is_unstarted

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.shared.application.queries.list_repo_sessions import AgentSessionDTO
    from grooveloop.shared.application.queries.query_bus import QueryBus
    from grooveloop.shared.domain.clock import Clock
    from grooveloop.shared.domain.loop_activity import LoopActivity
    from grooveloop.shared.domain.loop_heartbeat import LoopHeartbeat
    from grooveloop.shared.domain.loop_presence import LoopPresence
    from grooveloop.shared.domain.loop_signals import LoopSignal
    from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
    from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
    from grooveloop.shared.domain.process_liveness import ProcessLiveness
    from grooveloop.shared.domain.snapshot_tick import SnapshotTick

_FRESH_HEARTBEAT_SECONDS = 60
_LISTED_HEARTBEAT_SECONDS = 12 * 3600


@dataclass(frozen=True)
class TickDTO:
    outcome: str
    age_seconds: int
    duration_seconds: int

    @classmethod
    def from_domain(cls, tick: SnapshotTick, now: datetime) -> Self:
        return cls(
            outcome=tick.outcome.value,
            age_seconds=int((now - tick.at).total_seconds()),
            duration_seconds=tick.duration_seconds,
        )


@dataclass(frozen=True)
class SignalDTO:
    kind: str
    category: str
    reference: str | None = None

    @classmethod
    def from_domain(cls, signal: LoopSignal) -> Self:
        return cls(kind=signal.kind.value, category=signal.category.value, reference=signal.reference)


@dataclass(frozen=True)
class ActivityDTO:
    running: int
    elapsed_seconds: float
    cost_usd: float

    @classmethod
    def from_domain(cls, activity: LoopActivity) -> Self:
        return cls(
            running=activity.running,
            elapsed_seconds=activity.elapsed_seconds,
            cost_usd=activity.cost_usd,
        )


@dataclass(frozen=True)
class LoopDTO:
    repo: str
    alive: bool
    age_seconds: int
    tick: TickDTO | None = None
    signals: list[SignalDTO] = field(default_factory=list)
    activity: ActivityDTO | None = None
    sessions: list[AgentSessionDTO] = field(default_factory=list)

    @classmethod
    def from_domain(
        cls,
        heartbeat: LoopHeartbeat,
        now: datetime,
        *,
        running: bool,
        snapshot: LoopSnapshot | None,
        sessions: list[AgentSessionDTO],
        stall_after_seconds: int,
    ) -> Self:
        age_seconds = int((now - heartbeat.at).total_seconds())
        tick = TickDTO.from_domain(snapshot.tick, now) if snapshot is not None else None
        sliced = _sessions_of(sessions, snapshot)
        runs = _runs_of(sliced, now)
        activity = activity_of(runs)

        return cls(
            repo=heartbeat.repo,
            alive=running and age_seconds <= _FRESH_HEARTBEAT_SECONDS,
            age_seconds=age_seconds,
            tick=tick,
            signals=_signals_of(snapshot, tick, runs, stall_after_seconds),
            activity=ActivityDTO.from_domain(activity) if activity is not None else None,
            sessions=sliced,
        )


@dataclass(frozen=True)
class ListLoopsQueryResult(QueryResult):
    loops: list[LoopDTO]


@dataclass(frozen=True)
class ListLoopsQuery(Query[ListLoopsQueryResult]):
    stall_after_seconds: int


class ListLoopsQueryHandler(QueryHandler[ListLoopsQuery, ListLoopsQueryResult]):
    def __init__(
        self,
        loop_presence: LoopPresence,
        process_liveness: ProcessLiveness,
        loop_snapshots: LoopSnapshots,
        clock: Clock,
        query_bus: QueryBus,
    ) -> None:
        self._loop_presence = loop_presence
        self._process_liveness = process_liveness
        self._loop_snapshots = loop_snapshots
        self._clock = clock
        self._query_bus = query_bus

    def __call__(self, query: ListLoopsQuery) -> ListLoopsQueryResult:
        now = self._clock.now()
        loops = []
        for heartbeat in self._loop_presence.heartbeats():
            running = self._process_liveness.is_alive(heartbeat.pid)
            loops.append(
                LoopDTO.from_domain(
                    heartbeat,
                    now,
                    running=running,
                    snapshot=self._loop_snapshots.find(heartbeat.repo),
                    sessions=self._sessions_of(heartbeat.repo) if running else [],
                    stall_after_seconds=query.stall_after_seconds,
                )
            )

        listed = [loop for loop in loops if loop.age_seconds <= _LISTED_HEARTBEAT_SECONDS]

        return ListLoopsQueryResult(loops=sorted(listed, key=lambda loop: loop.repo))

    def _sessions_of(self, repo: str) -> list[AgentSessionDTO]:
        return self._query_bus.ask(ListRepoSessionsQuery(repo=repo)).sessions


def _sessions_of(sessions: list[AgentSessionDTO], snapshot: LoopSnapshot | None) -> list[AgentSessionDTO]:
    if snapshot is None:
        return []

    numbers = {a_slice.number for story in snapshot.stories for a_slice in story.slices}

    return [session for session in sessions if session.slice_number in numbers]


def _signals_of(
    snapshot: LoopSnapshot | None,
    tick: TickDTO | None,
    runs: list[LoopRun],
    stall_after_seconds: int,
) -> list[SignalDTO]:
    if snapshot is None or tick is None:
        return []

    return [
        SignalDTO.from_domain(signal) for signal in signals_of(snapshot, tick.age_seconds, runs, stall_after_seconds)
    ]


def _runs_of(sessions: list[AgentSessionDTO], now: datetime) -> list[LoopRun]:
    return [
        LoopRun(
            slice_number=session.slice_number,
            running=session.outcome == AgentOutcome.RUNNING.value
            and not is_unstarted(session.has_log, session.started_at, now),
            elapsed_seconds=session.elapsed_seconds,
            cost_usd=session.total_cost_usd or 0.0,
            silent_seconds=_silent_seconds(session, now),
        )
        for session in sessions
    ]


def _silent_seconds(session: AgentSessionDTO, now: datetime) -> float:
    if session.last_event_at is None:
        return 0.0

    return max(0.0, (now - session.last_event_at).total_seconds())

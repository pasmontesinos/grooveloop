from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from github import Github

from grooveloop.bootstrap import container
from grooveloop.cli import tick as tick_module
from grooveloop.cli.invocation_inputs import bind_invocation_inputs
from grooveloop.cli.preflight import ProbeStatus, run_preflight
from grooveloop.cli.story_snapshot import StorySnapshot
from grooveloop.cli.tick_pull_requests import PullRequestsSource, TickPullRequests
from grooveloop.cli.tick_snapshot import SnapshotSource, TickSnapshot
from grooveloop.cli.tick_specs import TickSpecs
from grooveloop.delivery.infrastructure.github_delivery_labels import GithubDeliveryLabels
from grooveloop.learning.application.queries.story_lessons import StoryLessonsQueryHandler
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.loop_presence import LoopPresence
from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
from grooveloop.shared.domain.pull_request_details import PullRequestDetails
from grooveloop.shared.domain.snapshot_tick import SnapshotTick
from grooveloop.shared.domain.story_specs import StorySpecs
from grooveloop.shared.domain.tick_outcome import TickOutcome
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode
from grooveloop.shared.infrastructure.github_pull_request_contents import GithubPullRequestContents
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph
from grooveloop.shared.infrastructure.target_repo import TargetRepo
from grooveloop.shared.infrastructure.target_repository import target_repository

if TYPE_CHECKING:
    from datetime import datetime

    from github.Repository import Repository


@dataclass(frozen=True)
class _TickResult:
    ok: bool
    at: datetime
    duration_seconds: int


@dataclass(frozen=True)
class _TickPublishers:
    snapshot: TickSnapshot
    pull_requests: TickPullRequests
    specs: TickSpecs


@dataclass(frozen=True)
class _TickInputs:
    repo_full_name: str
    workdir: str
    story: int | None
    verify_deploy: bool
    max_review_rounds: int
    max_parallel_slices: int
    journal_enabled: bool
    max_retries: int
    auto_merge: bool
    tick_interval: int


def run(
    repo_full_name: str,
    *,
    interval: int = 5,
    tick_interval: int = 600,
    workdir: str = ".",
    once: bool = False,
    story: int | None = None,
    verify_deploy: bool = False,
    max_review_rounds: int = 0,
    max_parallel_slices: int = 1,
    journal_enabled: bool = False,
    max_retries: int = 0,
    auto_merge: bool = False,
) -> int:
    bind_invocation_inputs(
        repo_full_name,
        workdir,
        verify_deploy=verify_deploy,
        max_review_rounds=max_review_rounds,
        max_parallel_slices=max_parallel_slices,
        journal_enabled=journal_enabled,
        max_retries=max_retries,
        auto_merge=auto_merge,
    )
    inputs = _TickInputs(
        repo_full_name=repo_full_name,
        workdir=workdir,
        story=story,
        verify_deploy=verify_deploy,
        max_review_rounds=max_review_rounds,
        max_parallel_slices=max_parallel_slices,
        journal_enabled=journal_enabled,
        max_retries=max_retries,
        auto_merge=auto_merge,
        tick_interval=tick_interval,
    )

    if not _preflight_passes(auto_merge):
        return ExitCode.PREFLIGHT_FAILED

    _ensure_delivery_labels(repo_full_name)

    clock = container.get(Clock)
    presence = container.get(LoopPresence)
    publishers = _build_tick_publishers(_repository(repo_full_name), repo_full_name, clock)

    _beat(presence, repo_full_name)
    if once:
        result = _tick(publishers, clock, inputs)

        return ExitCode.OK if result.ok else ExitCode.FAILURE

    return _follow(publishers, presence, interval, clock, inputs)


def _repository(repo_full_name: str) -> Repository | None:
    try:
        return target_repository(container.get(Github), container.get(TargetRepo), container.get(GithubReadCache))
    except Exception as error:
        print(f"[warn] target repository unavailable in {repo_full_name}: {error}", file=sys.stderr)

        return None


def _build_tick_publishers(repo: Repository | None, repo_full_name: str, clock: Clock) -> _TickPublishers:
    return _TickPublishers(
        snapshot=TickSnapshot(
            snapshots=container.get(LoopSnapshots),
            repo=repo_full_name,
            source=_snapshot_source(repo),
        ),
        pull_requests=TickPullRequests(
            details=container.get(PullRequestDetails),
            repo=repo_full_name,
            clock=clock,
            snapshots=container.get(LoopSnapshots),
            source=_pull_requests_source(repo),
        ),
        specs=TickSpecs(specs=container.get(StorySpecs), repo=repo_full_name, graph=_story_graph(repo)),
    )


def _snapshot_source(repo: Repository | None) -> SnapshotSource | None:
    if repo is None:
        return None

    return SnapshotSource(
        stories=StorySnapshot(GithubStoryGraph(repo, container.get(GithubReadCache))),
        lessons=container.get(StoryLessonsQueryHandler),
    )


def _pull_requests_source(repo: Repository | None) -> PullRequestsSource | None:
    if repo is None:
        return None

    return PullRequestsSource(
        graph=GithubStoryGraph(repo, container.get(GithubReadCache)),
        contents=GithubPullRequestContents(repo),
    )


def _story_graph(repo: Repository | None) -> GithubStoryGraph | None:
    if repo is None:
        return None

    return GithubStoryGraph(repo, container.get(GithubReadCache))


class _Heartbeat:
    def __init__(self, presence: LoopPresence, repo_full_name: str, interval: int) -> None:
        self._presence = presence
        self._repo_full_name = repo_full_name
        self._interval = interval
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._beat_until_stopped, name="grooveloop-heartbeat", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join()

    def _beat_until_stopped(self) -> None:
        while not self._stopped.wait(self._interval):
            _beat(self._presence, self._repo_full_name)


def _follow(
    publishers: _TickPublishers,
    presence: LoopPresence,
    interval: int,
    clock: Clock,
    inputs: _TickInputs,
) -> int:
    heartbeat = _Heartbeat(presence, inputs.repo_full_name, interval)
    heartbeat.start()
    try:
        last_tick = _tick(publishers, clock, inputs)
        while True:
            time.sleep(interval)
            if (clock.now() - last_tick.at).total_seconds() >= inputs.tick_interval:
                last_tick = _tick(publishers, clock, inputs)
    except KeyboardInterrupt:
        return ExitCode.OK
    finally:
        heartbeat.stop()


def _preflight_passes(auto_merge: bool) -> bool:
    report = run_preflight(with_merger=auto_merge)

    for outcome in report.outcomes:
        if outcome.status is not ProbeStatus.OK:
            print(outcome.line(), file=sys.stderr)

    return report.passed()


def _ensure_delivery_labels(repo_full_name: str) -> None:
    try:
        container.get(GithubDeliveryLabels).ensure()
    except Exception as error:
        print(f"[warn] delivery labels unavailable in {repo_full_name}: {error}", file=sys.stderr)


def _beat(presence: LoopPresence, repo_full_name: str) -> None:
    try:
        presence.beat(repo_full_name)
    except OSError as error:
        print(f"[warn] presence heartbeat failed in {repo_full_name}: {error}", file=sys.stderr)


def _tick(publishers: _TickPublishers, clock: Clock, inputs: _TickInputs) -> _TickResult:
    started_at = clock.now()
    try:
        ok = (
            tick_module.run(
                inputs.repo_full_name,
                inputs.workdir,
                story=inputs.story,
                verify_deploy=inputs.verify_deploy,
                max_review_rounds=inputs.max_review_rounds,
                max_parallel_slices=inputs.max_parallel_slices,
                journal_enabled=inputs.journal_enabled,
                max_retries=inputs.max_retries,
                auto_merge=inputs.auto_merge,
            )
            == 0
        )
    except Exception as error:
        print(f"[fail] run tick in {inputs.repo_full_name}: {error}", file=sys.stderr)
        ok = False

    ended_at = clock.now()
    result = _TickResult(ok=ok, at=ended_at, duration_seconds=int((ended_at - started_at).total_seconds()))
    _publish(publishers.snapshot, result, inputs.repo_full_name, inputs.tick_interval)
    publishers.pull_requests.publish()
    publishers.specs.publish()

    return result


def _publish(snapshot: TickSnapshot, result: _TickResult, repo_full_name: str, tick_interval: int) -> None:
    try:
        snapshot.publish(
            SnapshotTick(
                outcome=_outcome_of(result),
                at=result.at,
                duration_seconds=result.duration_seconds,
                interval_seconds=tick_interval,
            )
        )
    except OSError as error:
        print(f"[warn] tick snapshot failed in {repo_full_name}: {error}", file=sys.stderr)


def _outcome_of(last_tick: _TickResult) -> TickOutcome:
    return TickOutcome.OK if last_tick.ok else TickOutcome.FAILED

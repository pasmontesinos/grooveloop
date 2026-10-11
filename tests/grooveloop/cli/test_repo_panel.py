from __future__ import annotations

from datetime import UTC, datetime, timedelta

from grooveloop.cli.repo_panel import story_lines
from grooveloop.shared.application.queries.list_repo_sessions import AgentSessionDTO
from grooveloop.shared.domain.snapshot_lesson import SnapshotLesson
from grooveloop.shared.domain.snapshot_lesson_status import SnapshotLessonStatus
from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus

_NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


def _session(
    slice_number: str,
    outcome: str = "running",
    elapsed_seconds: float = 240.0,
    total_cost_usd: float | None = None,
    last_event_at: datetime | None = None,
    started_at: datetime = _NOW,
    has_log: bool = True,
    cause: str | None = None,
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
        launch_model="opus",
        last_event_at=last_event_at,
        cause=cause,
    )


def _slice(number: str, status: str, title: str, pr_number: str | None = None) -> SnapshotSlice:
    return SnapshotSlice(number=number, status=SnapshotSliceStatus(status), title=title, pr_number=pr_number)


def _story(
    slices: list[SnapshotSlice],
    lessons: list[SnapshotLesson] | None = None,
    title: str = "Panel multirepo",
) -> SnapshotStory:
    return SnapshotStory(
        number="338",
        status=SnapshotStoryStatus.SLICED,
        title=title,
        slices=slices,
        lessons=lessons or [],
    )


class TestRepoPanel:
    def test_should_order_the_slices_as_the_snapshot_lists_them(self) -> None:
        stories = story_lines(
            [_story([_slice("1", "merged", "snapshot local"), _slice("2", "pr_open", "lista de repos")])], [], _NOW
        )

        assert [(a_slice.order, a_slice.title) for a_slice in stories[0].slices] == [
            (1, "snapshot local"),
            (2, "lista de repos"),
        ]

    def test_should_attach_the_lesson_of_the_slice_that_sourced_it(self) -> None:
        lesson = SnapshotLesson(
            number="400",
            source_pull_request_number=342,
            status=SnapshotLessonStatus.LEARNED,
            conventions_pull_request_number=343,
            resolved=True,
        )
        stories = story_lines([_story([_slice("1", "merged", "snapshot local", pr_number="342")], [lesson])], [], _NOW)

        learning = stories[0].slices[0].learning
        assert learning is not None
        assert learning.number == "400"
        assert learning.conventions_pr_number == "343"
        assert learning.resolved is True
        assert stories[0].lessons == []

    def test_should_keep_a_lesson_without_its_slice_at_the_story_level(self) -> None:
        lesson = SnapshotLesson(
            number=None,
            source_pull_request_number=999,
            status=SnapshotLessonStatus.IN_PROGRESS,
            conventions_pull_request_number=None,
            resolved=False,
        )
        stories = story_lines([_story([_slice("1", "merged", "snapshot local", pr_number="342")], [lesson])], [], _NOW)

        assert stories[0].slices[0].learning is None
        assert [line.status for line in stories[0].lessons] == ["in_progress"]

    def test_should_leave_a_session_of_another_slice_out_of_the_slice(self) -> None:
        stories = story_lines([_story([_slice("350", "dispatched", "snapshot local")])], [_session("999")], _NOW)

        assert stories[0].slices[0].sessions == []

    def test_should_hang_the_session_of_a_slice_under_the_slice(self) -> None:
        stories = story_lines(
            [_story([_slice("350", "dispatched", "snapshot local")])], [_session("350", total_cost_usd=0.82)], _NOW
        )

        assert [session.total_cost_usd for session in stories[0].slices[0].sessions] == [0.82]

    def test_should_show_as_unstarted_a_session_without_log_started_more_than_five_minutes_ago(self) -> None:
        session = _session("350", has_log=False, started_at=_NOW - timedelta(minutes=6))

        stories = story_lines([_story([_slice("350", "dispatched", "snapshot local")])], [session], _NOW)

        assert [line.outcome for line in stories[0].slices[0].sessions] == ["unstarted"]

    def test_should_carry_the_outcome_and_cause_of_an_interrupted_session(self) -> None:
        session = _session("350", outcome="interrupted", cause="overloaded")

        stories = story_lines([_story([_slice("350", "dispatched", "snapshot local")])], [session], _NOW)

        assert [(line.outcome, line.cause) for line in stories[0].slices[0].sessions] == [("interrupted", "overloaded")]

    def test_should_keep_running_a_session_without_log_started_less_than_five_minutes_ago(self) -> None:
        session = _session("350", has_log=False, started_at=_NOW - timedelta(minutes=4))

        stories = story_lines([_story([_slice("350", "dispatched", "snapshot local")])], [session], _NOW)

        assert [line.outcome for line in stories[0].slices[0].sessions] == ["running"]

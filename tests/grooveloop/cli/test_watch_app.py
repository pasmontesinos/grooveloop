from __future__ import annotations

import asyncio
import re
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import StringIO
from itertools import pairwise
from typing import TYPE_CHECKING, Any

import pytest
from rich.console import Console
from textual.color import Color
from textual.containers import VerticalScroll
from textual.events import MouseScrollDown
from textual.geometry import Region
from textual.widgets import Footer, Markdown, OptionList, Static, Tab, TabbedContent, Tabs
from textual.widgets.markdown import MarkdownFence

from grooveloop.bootstrap import container
from grooveloop.cli.focus_path import FocusPath
from grooveloop.cli.pull_request_comments import PullRequestComments
from grooveloop.cli.pull_request_diff import PullRequestDiff, PullRequestFiles, PullRequestPatch
from grooveloop.cli.pull_request_panel import PullRequestBody, PullRequestPanel
from grooveloop.cli.run_log import RunLog
from grooveloop.cli.run_panel import RunPanel
from grooveloop.cli.slice_list import ListRow, SessionRow, SliceList, SliceRow
from grooveloop.cli.story_journal import (
    JournalEntries,
    JournalEntryBlock,
    JournalEntryHeader,
    JournalFilter,
    StoryJournal,
)
from grooveloop.cli.story_selector import StorySelector
from grooveloop.cli.story_spec import StorySpec
from grooveloop.cli.watch_app import CENTER_MIN_WIDTH, LoopsApp
from grooveloop.delivery.domain.agent_session import AgentSession
from grooveloop.delivery.domain.agent_session_repository import AgentSessionRepository
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.journal.domain.entry_kind import EntryKind
from grooveloop.journal.domain.journal_entry_repository import JournalEntryRepository
from grooveloop.shared.application.queries.list_loops import ListLoopsQueryHandler
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.domain.agent_log_action import AgentLogAction
from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_logs import AgentRunLogs
from grooveloop.shared.domain.agent_task_type import AgentTaskType
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.cost_basis import CostBasis
from grooveloop.shared.domain.cost_share import CostShare
from grooveloop.shared.domain.cost_split import CostSplit
from grooveloop.shared.domain.loop_heartbeat import LoopHeartbeat
from grooveloop.shared.domain.loop_presence import LoopPresence
from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
from grooveloop.shared.domain.model_usage import ModelUsage
from grooveloop.shared.domain.process_liveness import ProcessLiveness
from grooveloop.shared.domain.pull_request_comment import PullRequestComment
from grooveloop.shared.domain.pull_request_detail import PullRequestDetail
from grooveloop.shared.domain.pull_request_details import PullRequestDetails
from grooveloop.shared.domain.pull_request_file import PullRequestFile
from grooveloop.shared.domain.snapshot_lesson import SnapshotLesson
from grooveloop.shared.domain.snapshot_lesson_status import SnapshotLessonStatus
from grooveloop.shared.domain.snapshot_mergeability import SnapshotMergeability
from grooveloop.shared.domain.snapshot_pull_request import SnapshotPullRequest
from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus
from grooveloop.shared.domain.snapshot_tick import SnapshotTick
from grooveloop.shared.domain.story_specs import StorySpecs
from grooveloop.shared.domain.tick_outcome import TickOutcome
from grooveloop.shared.domain.token_class import TokenClass
from grooveloop.shared.domain.tool_tally import ToolTally
from tests.grooveloop.journal.mothers.journal_entry_mother import JournalEntryMother
from tests.playground.shared.infrastructure.clock import clock_at
from tests.playground.shared.infrastructure.fake_agent_run_logs import FakeAgentRunLogs
from tests.playground.shared.infrastructure.fake_agent_session_repository import FakeAgentSessionRepository
from tests.playground.shared.infrastructure.fake_journal_entry_repository import FakeJournalEntryRepository
from tests.playground.shared.infrastructure.fake_loop_presence import FakeLoopPresence, GatedLoopPresence
from tests.playground.shared.infrastructure.fake_loop_snapshots import FakeLoopSnapshots
from tests.playground.shared.infrastructure.fake_process_liveness import FakeProcessLiveness
from tests.playground.shared.infrastructure.fake_pull_request_details import FakePullRequestDetails
from tests.playground.shared.infrastructure.fake_story_specs import FakeStorySpecs

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from rich.segment import Segment
    from textual.pilot import Pilot
    from textual.widget import Widget

    from grooveloop.journal.domain.journal_entry import JournalEntry

_NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
_PAUSE_SECONDS = 0.01
_WAIT_STEPS = 100
_TIMER_SECONDS = 1
_SHORT_SCREEN = (120, 12)
_TALL_STORY_SLICES = 40
_GATE_SECONDS = 5


def _snapshot(repo: str, outcome: TickOutcome, stories: list[SnapshotStory] | None = None) -> LoopSnapshot:
    return LoopSnapshot(
        repo=repo,
        tick=SnapshotTick(outcome=outcome, at=_NOW, duration_seconds=38, interval_seconds=600),
        stories=stories or [],
    )


def _story(
    title: str,
    slice_count: int,
    number: str = "338",
    pr_number: str | None = None,
    first_slice: int = 350,
    status: str = "pr_open",
) -> SnapshotStory:
    return SnapshotStory(
        number=number,
        status=SnapshotStoryStatus.SLICED,
        title=title,
        slices=[
            SnapshotSlice(
                number=str(first_slice + order),
                status=SnapshotSliceStatus(status),
                title=f"slice {order}",
                pr_number=pr_number,
            )
            for order in range(slice_count)
        ],
        lessons=[],
    )


def _chain_story(title: str) -> SnapshotStory:
    return SnapshotStory(
        number="338",
        status=SnapshotStoryStatus.SLICED,
        title=title,
        slices=[
            SnapshotSlice(number="350", status=SnapshotSliceStatus.MERGED, title="base", pr_number=None),
            SnapshotSlice(
                number="351", status=SnapshotSliceStatus.PR_OPEN, title="middle", pr_number=None, depends_on=["350"]
            ),
            SnapshotSlice(
                number="352", status=SnapshotSliceStatus.PENDING, title="top", pr_number=None, depends_on=["350", "351"]
            ),
        ],
        lessons=[],
    )


def _chain_snapshot(title: str) -> LoopSnapshot:
    return _snapshot("verify/alfa", TickOutcome.OK, [_chain_story(title)])


def _running_session(slice_id: str, silent_seconds: int, run_id: str = "run-1") -> AgentSession:
    return AgentSession(
        slice_id=SliceId(slice_id),
        outcome=AgentOutcome.RUNNING,
        task_type=AgentTaskType.IMPLEMENT_SLICE,
        engine="claude",
        run_id=run_id,
        started_at=_NOW,
        has_log=True,
        elapsed_seconds=600.0,
        last_event_at=_NOW - timedelta(seconds=silent_seconds),
    )


@pytest.fixture
def one_alive_and_one_idle_loop() -> Any:
    presence = FakeLoopPresence(
        [
            LoopHeartbeat(repo="verify/alfa", pid=100, at=_NOW - timedelta(seconds=2)),
            LoopHeartbeat(repo="acme/shop", pid=101, at=_NOW - timedelta(seconds=2820)),
        ]
    )
    snapshots = FakeLoopSnapshots([_snapshot("verify/alfa", TickOutcome.OK)])
    with (
        container.override(LoopPresence, presence),
        container.override(ProcessLiveness, FakeProcessLiveness([100])),
        container.override(LoopSnapshots, snapshots),
        container.override(AgentSessionRepository, FakeAgentSessionRepository({})),
        container.override(Clock, clock_at(_NOW)),
    ):
        yield snapshots


@pytest.fixture
def one_alive_loop_with_two_stories() -> Any:
    presence = FakeLoopPresence([LoopHeartbeat(repo="verify/alfa", pid=100, at=_NOW - timedelta(seconds=2))])
    snapshots = FakeLoopSnapshots(
        [
            _snapshot(
                "verify/alfa",
                TickOutcome.OK,
                [
                    _story("Alfa story", _TALL_STORY_SLICES, pr_number="61"),
                    _story("Gamma story", 1, number="339", first_slice=400),
                ],
            )
        ]
    )
    with (
        container.override(LoopPresence, presence),
        container.override(ProcessLiveness, FakeProcessLiveness([100])),
        container.override(LoopSnapshots, snapshots),
        container.override(AgentSessionRepository, FakeAgentSessionRepository({})),
        container.override(Clock, clock_at(_NOW)),
    ):
        yield snapshots


@pytest.fixture
def one_alive_loop_with_a_dependency_chain() -> Any:
    presence = FakeLoopPresence([LoopHeartbeat(repo="verify/alfa", pid=100, at=_NOW - timedelta(seconds=2))])
    snapshots = FakeLoopSnapshots([_chain_snapshot("Chain story")])
    with (
        container.override(LoopPresence, presence),
        container.override(ProcessLiveness, FakeProcessLiveness([100])),
        container.override(LoopSnapshots, snapshots),
        container.override(AgentSessionRepository, FakeAgentSessionRepository({})),
        container.override(Clock, clock_at(_NOW)),
    ):
        yield snapshots


@pytest.fixture
def two_alive_loops_with_a_tall_panel_and_a_silent_agent() -> Any:
    presence = FakeLoopPresence(
        [
            LoopHeartbeat(repo="verify/alfa", pid=100, at=_NOW - timedelta(seconds=2)),
            LoopHeartbeat(repo="verify/beta", pid=101, at=_NOW - timedelta(seconds=2)),
        ]
    )
    snapshots = FakeLoopSnapshots(
        [
            _snapshot("verify/alfa", TickOutcome.OK, [_story("Alfa story", _TALL_STORY_SLICES)]),
            _snapshot("verify/beta", TickOutcome.OK, [_story("Beta story", 1)]),
        ]
    )
    sessions = FakeAgentSessionRepository({("verify/alfa", "350"): [_running_session("350", silent_seconds=400)]})
    with (
        container.override(LoopPresence, presence),
        container.override(ProcessLiveness, FakeProcessLiveness([100, 101])),
        container.override(LoopSnapshots, snapshots),
        container.override(AgentSessionRepository, sessions),
        container.override(Clock, clock_at(_NOW)),
    ):
        yield snapshots


@pytest.fixture
def one_alive_loop_whose_refresh_is_held() -> Any:
    presence = GatedLoopPresence(
        [LoopHeartbeat(repo="verify/alfa", pid=100, at=_NOW - timedelta(seconds=2))], gate_seconds=_GATE_SECONDS
    )
    snapshots = FakeLoopSnapshots([_snapshot("verify/alfa", TickOutcome.OK, [_story("Alfa story", 3)])])
    with (
        container.override(LoopPresence, presence),
        container.override(ProcessLiveness, FakeProcessLiveness([100])),
        container.override(LoopSnapshots, snapshots),
        container.override(AgentSessionRepository, FakeAgentSessionRepository({})),
        container.override(Clock, clock_at(_NOW)),
    ):
        yield presence


def _app(interval: float = 60) -> LoopsApp:
    return LoopsApp(
        container.get(ListLoopsQueryHandler),
        container.get(LoopSnapshots),
        container.get(PullRequestDetails),
        container.get(AgentRunLogs),
        container.get(StorySpecs),
        container.get(QueryBus),
        container.get(Clock),
        interval=interval,
        stall_after=300,
    )


def _plain_text(static: Static) -> str:
    return _render_plain(static.content)


def _render_plain(renderable: Any) -> str:
    buffer = StringIO()
    Console(file=buffer, width=400, color_system=None).print(renderable)

    return buffer.getvalue()


def _loop_list(app: LoopsApp) -> OptionList:
    return app.query_one("#loop-list", OptionList)


def _loops_text(app: LoopsApp) -> str:
    options = "".join(_render_plain(option.prompt) for option in _loop_list(app).options)

    return _plain_text(app.query_one("#loops-title", Static)) + options


def _panel_text(app: LoopsApp) -> str:
    return "".join(_plain_text(line) for line in app.query_one(SliceList).query_children(Static))


def _row(app: LoopsApp, number: str) -> SliceRow:
    return app.query_one(f"#slice-{number}", SliceRow)


def _highlighted(app: LoopsApp) -> list[str | None]:
    return [row.id for row in app.query(SliceRow) if row.has_class("-highlighted")]


def _marks(app: LoopsApp) -> dict[str, str]:
    return {
        str(row.id): mark
        for row in app.query(SliceRow)
        for mark, css_class in (("▲", "-needed"), ("▼", "-unblocked"))
        if row.has_class(css_class) and mark in _plain_text(row)
    }


def _run_lines(app: LoopsApp) -> list[str]:
    return [
        strip.text
        for row in app.query(SessionRow)
        for strip in row.render_lines(Region(0, 0, row.size.width, row.size.height))
        if "⏱" in strip.text
    ]


def _link_offset(widget: Widget, fragment: str) -> tuple[int, int]:
    for y, strip in enumerate(widget.render_lines(Region(0, 0, widget.size.width, widget.size.height))):
        x = 0
        for segment in strip:
            if segment.style is not None and segment.style.link is not None and fragment in segment.style.link:
                return x, y

            x += segment.cell_length

    raise AssertionError(fragment)


def _click_offset(widget: Widget, fragment: str) -> tuple[int, int]:
    for y, strip in enumerate(widget.render_lines(Region(0, 0, widget.size.width, widget.size.height))):
        x = 0
        for segment in strip:
            if segment.style is not None and fragment in str(segment.style.meta.get("@click", "")):
                return x, y

            x += segment.cell_length

    raise AssertionError(fragment)


async def _wait_for(pilot: Pilot[int], condition: Callable[[], bool]) -> None:
    for _ in range(_WAIT_STEPS):
        await pilot.pause(_PAUSE_SECONDS)
        if condition():
            return


async def _refresh(app: LoopsApp, pilot: Pilot[int]) -> None:
    await app._apply_loops(app._read_loops())
    await pilot.pause()


class TestLoopsApp:
    def test_should_list_the_alive_loop_with_the_outcome_of_its_last_tick(
        self, one_alive_and_one_idle_loop: Any
    ) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test():
                return _loops_text(app)

        text = asyncio.run(scenario())

        assert "verify/alfa" in text
        assert "tick ok · 0s ago · 38s" in text

    def test_should_list_the_idle_loop_under_its_own_heading(self, one_alive_and_one_idle_loop: Any) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test():
                return _loops_text(app)

        idle_block = asyncio.run(scenario()).split("NO LOOP")[1]

        assert "acme/shop" in idle_block
        assert "47m ago" in idle_block

    def test_should_refresh_the_list_when_the_snapshot_of_a_loop_changes(
        self, one_alive_and_one_idle_loop: Any
    ) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test() as pilot:
                one_alive_and_one_idle_loop.publish(_snapshot("verify/alfa", TickOutcome.FAILED))
                await _refresh(app, pilot)

                return _loops_text(app)

        assert "tick FAILED" in asyncio.run(scenario())

    def test_should_keep_the_idle_loop_out_of_reach_of_the_selection(self, one_alive_and_one_idle_loop: Any) -> None:
        async def scenario() -> list[tuple[str | None, bool]]:
            app = _app()
            async with app.run_test():
                return [(option.id, option.disabled) for option in _loop_list(app).options]

        options = dict(asyncio.run(scenario()))

        assert options["verify/alfa"] is False
        assert options["acme/shop"] is True

    def test_should_drop_the_position_keys_from_the_list(self, one_alive_and_one_idle_loop: Any) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test():
                return _loops_text(app)

        assert "[1-9]" not in asyncio.run(scenario())

    def test_should_show_the_keys_of_the_app_in_the_footer(self, one_alive_and_one_idle_loop: Any) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test():
                app.query_one(Footer)

                return [binding.key for (_, binding, enabled, _) in app.active_bindings.values() if binding.show]

        keys = asyncio.run(scenario())

        assert "q" in keys
        assert "enter" in keys
        assert "tab" in keys

    def test_should_exit_with_zero_when_the_user_presses_q(self, one_alive_and_one_idle_loop: Any) -> None:
        async def scenario() -> int | None:
            app = _app()
            async with app.run_test() as pilot:
                await pilot.press("q")

            return app.return_code

        assert asyncio.run(scenario()) == 0


class TestLoopsAppRefresh:
    def test_should_refresh_the_list_on_every_interval(self, one_alive_and_one_idle_loop: Any) -> None:
        async def scenario() -> str:
            app = _app(interval=_TIMER_SECONDS)
            async with app.run_test() as pilot:
                one_alive_and_one_idle_loop.publish(_snapshot("verify/alfa", TickOutcome.FAILED))
                await pilot.pause(_TIMER_SECONDS)
                await _wait_for(pilot, lambda: "tick FAILED" in _loops_text(app))

                return _loops_text(app)

        assert "tick FAILED" in asyncio.run(scenario())

    def test_should_move_the_highlight_while_the_refresh_is_still_reading_the_loops(
        self, one_alive_loop_whose_refresh_is_held: Any
    ) -> None:
        async def scenario() -> tuple[list[str | None], int]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                app._refresh_loops()
                await _wait_for(pilot, one_alive_loop_whose_refresh_is_held.held.is_set)
                await pilot.press("tab", "down")
                highlighted = _highlighted(app)
                in_flight = one_alive_loop_whose_refresh_is_held.in_flight
                one_alive_loop_whose_refresh_is_held.open()

                return highlighted, in_flight

        highlighted, in_flight = asyncio.run(scenario())

        assert highlighted == ["slice-351"]
        assert in_flight == 1

    def test_should_skip_the_refreshes_that_come_while_one_is_still_reading_the_loops(
        self, one_alive_loop_whose_refresh_is_held: Any
    ) -> None:
        async def scenario() -> tuple[int, int]:
            app = _app()
            async with app.run_test() as pilot:
                app._refresh_loops()
                await _wait_for(pilot, one_alive_loop_whose_refresh_is_held.held.is_set)
                app._refresh_loops()
                app._refresh_loops()
                await pilot.pause()
                reads = one_alive_loop_whose_refresh_is_held.reads
                one_alive_loop_whose_refresh_is_held.open()

                return reads, one_alive_loop_whose_refresh_is_held.max_in_flight

        reads, max_in_flight = asyncio.run(scenario())

        assert reads == 2
        assert max_in_flight == 1


class TestLoopsAppRepoPanel:
    def test_should_preselect_the_first_alive_loop_and_open_its_panel(
        self, two_alive_loops_with_a_tall_panel_and_a_silent_agent: Any
    ) -> None:
        async def scenario() -> tuple[str, str]:
            app = _app()
            async with app.run_test():
                return _loops_text(app), _panel_text(app)

        loops, panel = asyncio.run(scenario())

        assert "\u25b6 verify/alfa" in loops
        assert "Alfa story" in panel

    def test_should_open_the_panel_of_the_loop_the_user_reaches_with_the_arrows_and_enter(
        self, two_alive_loops_with_a_tall_panel_and_a_silent_agent: Any
    ) -> None:
        async def scenario() -> tuple[str, str]:
            app = _app()
            async with app.run_test() as pilot:
                await pilot.press("down", "enter")

                return _loops_text(app), _panel_text(app)

        loops, panel = asyncio.run(scenario())

        assert "\u25b6 verify/beta" in loops
        assert "Beta story" in panel

    def test_should_open_the_panel_of_the_loop_the_user_clicks(
        self, two_alive_loops_with_a_tall_panel_and_a_silent_agent: Any
    ) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                last_row = _loop_list(app).region.height - 2
                await pilot.click("#loop-list", offset=(4, last_row))

                return _panel_text(app)

        assert "Beta story" in asyncio.run(scenario())

    def test_should_keep_the_selection_on_the_same_repo_when_the_order_of_the_loops_changes(self) -> None:
        heartbeats = [
            LoopHeartbeat(repo="verify/alfa", pid=100, at=_NOW - timedelta(seconds=2)),
            LoopHeartbeat(repo="verify/beta", pid=101, at=_NOW - timedelta(seconds=2)),
        ]
        snapshots = FakeLoopSnapshots(
            [
                _snapshot("verify/alfa", TickOutcome.OK, [_story("Alfa story", 1)]),
                _snapshot("verify/beta", TickOutcome.OK, [_story("Beta story", 1)]),
            ]
        )

        async def scenario() -> tuple[list[str | None], str, str | None]:
            app = _app()
            async with app.run_test() as pilot:
                await pilot.press("down", "enter")
                heartbeats.append(LoopHeartbeat(repo="verify/aaa", pid=102, at=_NOW - timedelta(seconds=2)))
                await _refresh(app, pilot)

                highlighted = _loop_list(app).highlighted_option
                order = [option.id for option in _loop_list(app).options]

                return order, _panel_text(app), highlighted.id if highlighted is not None else None

        with (
            container.override(LoopPresence, FakeLoopPresence(heartbeats)),
            container.override(ProcessLiveness, FakeProcessLiveness([100, 101, 102])),
            container.override(LoopSnapshots, snapshots),
            container.override(AgentSessionRepository, FakeAgentSessionRepository({})),
            container.override(Clock, clock_at(_NOW)),
        ):
            order, panel, highlighted = asyncio.run(scenario())

        assert order == ["verify/aaa", "verify/alfa", "verify/beta"]
        assert "Beta story" in panel
        assert highlighted == "verify/beta"

    def test_should_fit_the_panel_to_the_width_of_its_widget(
        self, two_alive_loops_with_a_tall_panel_and_a_silent_agent: Any
    ) -> None:
        async def scenario() -> float:
            app = _app()
            async with app.run_test(size=(100, 40)) as pilot:
                await pilot.pause()

                return app.query_one("#panel", VerticalScroll).max_scroll_x

        assert asyncio.run(scenario()) == 0

    def test_should_scroll_a_tall_panel_with_the_cursor_keys(
        self, two_alive_loops_with_a_tall_panel_and_a_silent_agent: Any
    ) -> None:
        async def scenario() -> float:
            app = _app()
            async with app.run_test(size=_SHORT_SCREEN) as pilot:
                await pilot.press("tab", *["down"] * _SHORT_SCREEN[1])

                return app.query_one("#panel", VerticalScroll).scroll_y

        assert asyncio.run(scenario()) > 0

    def test_should_scroll_a_tall_panel_with_the_mouse_wheel(
        self, two_alive_loops_with_a_tall_panel_and_a_silent_agent: Any
    ) -> None:
        async def scenario() -> float:
            app = _app()
            async with app.run_test(size=_SHORT_SCREEN) as pilot:
                scroll = app.query_one("#panel", VerticalScroll)
                await pilot.pause()
                scroll.post_message(MouseScrollDown(scroll, 1, 1, 0, 1, 0, False, False, False))
                await pilot.pause()

                return scroll.scroll_y

        assert asyncio.run(scenario()) > 0

    def test_should_mark_the_agent_that_stayed_silent_past_the_threshold(
        self, two_alive_loops_with_a_tall_panel_and_a_silent_agent: Any
    ) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)):
                return _panel_text(app)

        assert "stalled" in asyncio.run(scenario())


class TestLoopsAppSliceList:
    def test_should_head_the_slices_of_the_chosen_story_with_its_number_and_title(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)):
                return _plain_text(app.query_one("#story-338", Static))

        assert "#338  Alfa story" in asyncio.run(scenario())

    def test_should_give_each_slice_a_row_with_its_order_and_title_before_its_status_and_pull_request(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)):
                return _plain_text(_row(app, "351"))

        line = asyncio.run(scenario()).splitlines()[0]

        assert line.split()[:3] == ["2", "slice", "1"]
        assert line.index("slice 1") < line.index("pr_open") < line.index("#61")

    def test_should_give_each_run_its_own_line_indented_under_the_title_of_its_slice(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        sessions = FakeAgentSessionRepository(
            {
                ("verify/alfa", "350"): [
                    _running_session("350", silent_seconds=0, run_id="run-1"),
                    _running_session("350", silent_seconds=0, run_id="run-2"),
                ]
            }
        )

        async def scenario() -> tuple[str, list[str]]:
            app = _app()
            async with app.run_test(size=(160, 40)):
                return _plain_text(_row(app, "350")), [_plain_text(row) for row in app.query(SessionRow)]

        with container.override(AgentSessionRepository, sessions):
            slice_line, run_rows = asyncio.run(scenario())

        title_column = slice_line.index("slice 0")
        runs = [line for row in run_rows for line in row.splitlines() if "implement_slice" in line]
        assert len(runs) == 2
        assert all(len(line) - len(line.lstrip()) >= title_column for line in runs)

    def test_should_leave_the_pull_request_of_the_slice_out_of_the_line_of_its_run(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        sessions = FakeAgentSessionRepository({("verify/alfa", "351"): [_running_session("351", silent_seconds=0)]})

        async def scenario() -> tuple[str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)):
                return _plain_text(_row(app, "351")), _plain_text(app.query_one(SessionRow))

        with container.override(AgentSessionRepository, sessions):
            slice_line, run_line = asyncio.run(scenario())

        assert "#61" in slice_line
        assert "implement_slice" in run_line
        assert "#61" not in run_line

    def test_should_hide_the_same_columns_of_every_run_until_the_panel_widens(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        sessions = FakeAgentSessionRepository(
            {
                ("verify/alfa", "350"): [
                    replace(_running_session("350", 0, "run-1"), turns=163, tools=[ToolTally("Bash", 207)]),
                    replace(_running_session("350", 0, "run-2"), turns=3, tools=[ToolTally("Bash", 7)]),
                ]
            }
        )

        async def scenario() -> tuple[list[str], list[str]]:
            app = _app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                narrow = _run_lines(app)
                await pilot.resize_terminal(400, 40)
                await pilot.pause()

                return narrow, _run_lines(app)

        with container.override(AgentSessionRepository, sessions):
            narrow, wide = asyncio.run(scenario())

        assert all("tl" not in line for line in narrow)
        assert narrow[0].index("⏱") == narrow[1].index("⏱")
        assert all("tl" in line for line in wide)

    def test_should_highlight_the_first_slice_when_the_list_opens(self, one_alive_loop_with_two_stories: Any) -> None:
        async def scenario() -> list[str | None]:
            app = _app()
            async with app.run_test():
                return _highlighted(app)

        assert asyncio.run(scenario()) == ["slice-350"]

    def test_should_move_the_highlight_with_the_cursor_keys(self, one_alive_loop_with_two_stories: Any) -> None:
        async def scenario() -> list[str | None]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down", "down", "down", "up")

                return _highlighted(app)

        assert asyncio.run(scenario()) == ["slice-352"]

    def test_should_highlight_the_slice_the_user_clicks(self, one_alive_loop_with_two_stories: Any) -> None:
        async def scenario() -> tuple[list[str | None], bool]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                await pilot.click(_row(app, "353"), offset=(1, 0))

                return _highlighted(app), app.query_one(SliceList).has_focus

        highlighted, focused = asyncio.run(scenario())

        assert highlighted == ["slice-353"]
        assert focused is True

    def test_should_keep_the_highlighted_slice_and_the_scroll_after_a_refresh(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> tuple[list[str | None], float, float, str]:
            app = _app()
            async with app.run_test(size=_SHORT_SCREEN) as pilot:
                await pilot.press("tab", *["down"] * 10)
                scroll = app.query_one("#panel", VerticalScroll)
                scroll_y = scroll.scroll_y
                one_alive_loop_with_two_stories.publish(
                    _snapshot(
                        "verify/alfa",
                        TickOutcome.OK,
                        [
                            _story("Alfa renamed", _TALL_STORY_SLICES),
                            _story("Gamma story", 1, number="339", first_slice=400),
                        ],
                    )
                )
                await _refresh(app, pilot)

                return _highlighted(app), scroll_y, scroll.scroll_y - scroll_y, _panel_text(app)

        highlighted, scroll_y, scroll_shift, text = asyncio.run(scenario())

        assert "Alfa renamed" in text
        assert highlighted == ["slice-360"]
        assert scroll_y > 0
        assert scroll_shift == 0

    def test_should_not_open_the_issue_of_the_story_the_user_clicks(
        self, one_alive_loop_with_two_stories: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[str] = []

        async def scenario() -> None:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                heading = app.query_one("#story-338", Static)
                await pilot.click(heading, offset=_link_offset(heading, "/issues/338"))
                await pilot.pause()

        asyncio.run(scenario())

        assert opened == []

    def test_should_focus_the_row_of_the_pull_request_number_the_user_clicks_without_opening_it(
        self, one_alive_loop_with_two_stories: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[str] = []

        async def scenario() -> tuple[list[str | None], bool]:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                row = _row(app, "351")
                await pilot.click(row, offset=_link_offset(row, "/pull/61"))
                await pilot.pause()

                return _highlighted_rows(app), app.query_one(SliceList).has_focus

        highlighted, focused = asyncio.run(scenario())

        assert opened == []
        assert highlighted == ["slice-351"]
        assert focused is True


class TestLoopsAppSliceDependencies:
    def test_should_show_the_order_of_the_slices_a_slice_depends_on_between_its_title_and_its_status(
        self, one_alive_loop_with_a_dependency_chain: Any
    ) -> None:
        async def scenario() -> tuple[str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)):
                return _plain_text(_row(app, "350")), _plain_text(_row(app, "352"))

        base, top = asyncio.run(scenario())

        assert "←" not in base
        assert top.index("top") < top.index("← 1, 2") < top.index("pending")

    def test_should_mark_what_the_focused_slice_needs_and_what_it_unblocks(
        self, one_alive_loop_with_a_dependency_chain: Any
    ) -> None:
        async def scenario() -> dict[str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")

                return _marks(app)

        assert asyncio.run(scenario()) == {"slice-350": "▲", "slice-352": "▼"}

    def test_should_clear_the_previous_marks_when_the_focus_moves(
        self, one_alive_loop_with_a_dependency_chain: Any
    ) -> None:
        async def scenario() -> dict[str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down", "up")

                return _marks(app)

        assert asyncio.run(scenario()) == {"slice-351": "▼", "slice-352": "▼"}

    def test_should_keep_the_marks_of_the_focused_slice_after_a_refresh(
        self, one_alive_loop_with_a_dependency_chain: Any
    ) -> None:
        async def scenario() -> dict[str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down", "down")
                one_alive_loop_with_a_dependency_chain.publish(_chain_snapshot("Chain renamed"))
                await _refresh(app, pilot)

                return _marks(app)

        assert asyncio.run(scenario()) == {"slice-350": "▲", "slice-351": "▲"}

    def test_should_mark_the_dependencies_of_the_focused_slice_of_the_chosen_story(self) -> None:
        stories = [_story("Alfa story", 1, number="337", first_slice=300, status="dispatched"), _chain_story("Chain")]

        async def scenario() -> tuple[dict[str, str], str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("right_square_bracket")
                await _wait_for(pilot, lambda: _shown_stories(app) == ["story-338"])
                await pilot.press("tab", "down")

                return _marks(app), _plain_text(_row(app, "352"))

        with _one_alive_loop_with(stories):
            marks, top = asyncio.run(scenario())

        assert marks == {"slice-350": "▲", "slice-352": "▼"}
        assert "← 1, 2" in top


def _selector(app: LoopsApp) -> StorySelector:
    return app.query_one(StorySelector)


def _selector_labels(app: LoopsApp) -> list[str]:
    return [_render_plain(option.prompt).strip() for option in _selector(app).query_one(OptionList).options]


def _selector_current(app: LoopsApp) -> str:
    return _plain_text(_selector(app).query_one("#label", Static)).strip()


def _shown_stories(app: LoopsApp) -> list[str | None]:
    return [heading.id for heading in app.query_one(SliceList).query_children("StoryHeading")]


def _focus_path(app: LoopsApp) -> str:
    return _plain_text(app.query_one(FocusPath)).strip()


@contextmanager
def _one_alive_loop_with(stories: list[SnapshotStory]) -> Iterator[None]:
    presence = FakeLoopPresence([LoopHeartbeat(repo="verify/alfa", pid=100, at=_NOW - timedelta(seconds=2))])
    with (
        container.override(LoopPresence, presence),
        container.override(ProcessLiveness, FakeProcessLiveness([100])),
        container.override(LoopSnapshots, FakeLoopSnapshots([_snapshot("verify/alfa", TickOutcome.OK, stories)])),
        container.override(AgentSessionRepository, FakeAgentSessionRepository({})),
        container.override(Clock, clock_at(_NOW)),
    ):
        yield


class TestLoopsAppStorySelector:
    def test_should_show_the_single_listed_story_in_a_selector_that_does_not_expand(self) -> None:
        async def scenario() -> tuple[bool, str, bool, list[str | None]]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                await pilot.click(StorySelector)
                await pilot.pause()

                return _selector(app).display, _selector_current(app), _selector(app).expanded, _shown_stories(app)

        with _one_alive_loop_with([_story("Alfa story", 2)]):
            displayed, current, expanded, shown = asyncio.run(scenario())

        assert displayed is True
        assert current == "#338 Alfa story ⏳"
        assert expanded is False
        assert shown == ["story-338"]

    def test_should_offer_each_listed_story_with_its_number_title_and_signal(self) -> None:
        stories = [
            _story("Alfa story", 2, status="dispatched"),
            _story("Gamma story", 1, number="339", first_slice=400, status="pr_open"),
            _story("Delta story", 1, number="340", first_slice=500, status="blocked"),
        ]

        async def scenario() -> tuple[str, list[str]]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _selector_current(app), _selector_labels(app)

        with _one_alive_loop_with(stories):
            current, labels = asyncio.run(scenario())

        assert current == "#338 Alfa story ▶2"
        assert labels == ["#338 Alfa story ▶2", "#339 Gamma story ⏳", "#340 Delta story ⛔"]

    def test_should_show_only_the_slices_of_the_chosen_story(self, one_alive_loop_with_two_stories: Any) -> None:
        async def scenario() -> tuple[list[str | None], bool]:
            app = _app()
            async with app.run_test(size=(160, 40)):
                return _shown_stories(app), len(app.query("#slice-400")) > 0

        shown, gamma_row = asyncio.run(scenario())

        assert shown == ["story-338"]
        assert gamma_row is False

    def test_should_show_the_slices_spec_and_journal_of_the_story_the_user_picks_in_the_selector(self) -> None:
        stories = [_story("Alfa story", 1), _story("Gamma story", 1, number="339", first_slice=400)]
        gamma_note = _journal_entry(EntryKind.DECISION, "human", "Gamma decide.", 3, story_id="339")

        async def scenario() -> tuple[list[str | None], str | None, str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                await pilot.click(StorySelector)
                await pilot.pause()
                await pilot.press("down", "enter")
                await _wait_for(pilot, lambda: _shown_stories(app) == ["story-339"])

                return (
                    _shown_stories(app),
                    _selector(app).selection,
                    _spec_body(app).source,
                    _story_tab_labels(app)[2],
                )

        with (
            _one_alive_loop_with(stories),
            _specs_with({338: "Alfa spec", 339: "Gamma spec"}),
            _journal_with([gamma_note]),
        ):
            shown, selection, spec, journal_label = asyncio.run(scenario())

        assert shown == ["story-339"]
        assert selection == "339"
        assert spec == "Gamma spec"
        assert journal_label == "Journal 1"

    def test_should_give_the_focus_back_to_the_slice_list_after_picking_a_story_in_the_selector(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> Widget | None:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab")
                await pilot.click(StorySelector)
                await pilot.pause()
                await pilot.press("down", "enter")
                await _wait_for(pilot, lambda: _shown_stories(app) == ["story-339"])
                await pilot.pause()

                return app.focused

        focused = asyncio.run(scenario())

        assert isinstance(focused, SliceList)

    def test_should_move_to_the_next_and_the_previous_story_with_the_brackets(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> tuple[list[str | None], str, list[str | None], str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("right_square_bracket")
                await _wait_for(pilot, lambda: _shown_stories(app) == ["story-339"])
                after_next = (_shown_stories(app), _selector_current(app))
                await pilot.press("left_square_bracket")
                await _wait_for(pilot, lambda: _shown_stories(app) == ["story-338"])

                return *after_next, _shown_stories(app), _selector_current(app)

        after_next, current_after_next, after_previous, current_after_previous = asyncio.run(scenario())

        assert after_next == ["story-339"]
        assert current_after_next == "#339 Gamma story ⏳"
        assert after_previous == ["story-338"]
        assert current_after_previous == "#338 Alfa story ⏳"

    def test_should_keep_the_chosen_story_after_a_refresh_that_reorders_the_stories(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> tuple[list[str | None], list[str], str | None, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("right_square_bracket")
                await _wait_for(pilot, lambda: _shown_stories(app) == ["story-339"])
                one_alive_loop_with_two_stories.publish(
                    _snapshot(
                        "verify/alfa",
                        TickOutcome.OK,
                        [
                            _story("Gamma renamed", 1, number="339", first_slice=400),
                            _story("Alfa story", 2, pr_number="61"),
                        ],
                    )
                )
                await _refresh(app, pilot)

                return _shown_stories(app), _selector_labels(app), _selector(app).selection, _selector_current(app)

        shown, labels, selection, current = asyncio.run(scenario())

        assert labels[0].startswith("#339 Gamma renamed")
        assert shown == ["story-339"]
        assert selection == "339"
        assert current == "#339 Gamma renamed ⏳"

    def test_should_keep_the_story_the_user_chose_when_the_panel_repaints_before_hearing_of_the_choice(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> tuple[list[str | None], str | None]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                loop_list = _loop_list(app)
                app.action_next_story()
                await app.on_option_list_option_selected(
                    OptionList.OptionSelected(loop_list, loop_list.get_option_at_index(0), 0)
                )
                await pilot.pause()

                return _shown_stories(app), _selector(app).selection

        shown, selection = asyncio.run(scenario())

        assert shown == ["story-339"]
        assert selection == "339"

    def test_should_hold_the_slice_list_in_a_slices_tab(self, one_alive_loop_with_two_stories: Any) -> None:
        async def scenario() -> tuple[list[str], int]:
            app = _app()
            async with app.run_test(size=(160, 40)):
                content = app.query_one(TabbedContent)
                labels = [tab.label_text for tab in content.query_one(Tabs).query("Tab").results(Tab)]

                return labels, len(content.query(SliceList))

        labels, lists = asyncio.run(scenario())

        assert labels == ["Slices", "Spec", "Journal 0"]
        assert lists == 1

    def test_should_keep_tab_jumping_from_the_loops_to_the_slice_list(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> bool:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab")

                return app.query_one(SliceList).has_focus

        assert asyncio.run(scenario()) is True

    def test_should_show_the_path_of_the_focused_slice_in_the_top_bar(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> tuple[str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                first = _focus_path(app)
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: _focus_path(app) != first)

                return first, _focus_path(app)

        first, moved = asyncio.run(scenario())

        assert first == "verify/alfa \u203a #338 Alfa story \u203a 1 slice 0"
        assert moved == "verify/alfa \u203a #338 Alfa story \u203a 2 slice 1"


def _reviewed_story() -> SnapshotStory:
    return SnapshotStory(
        number="338",
        status=SnapshotStoryStatus.SLICED,
        title="Reviewed story",
        slices=[
            SnapshotSlice(
                number="350",
                status=SnapshotSliceStatus.PR_OPEN,
                title="Roles",
                pr_number="61",
                pull_request=SnapshotPullRequest(
                    title="Member roles",
                    additions=180,
                    deletions=22,
                    changed_files=7,
                    updated_at=_NOW - timedelta(seconds=40),
                    head_ref_oid="abc123",
                    mergeable=SnapshotMergeability.MERGEABLE,
                    checks="success",
                ),
            ),
            SnapshotSlice(
                number="351",
                status=SnapshotSliceStatus.PR_OPEN,
                title="Permissions",
                pr_number="62",
                pull_request=SnapshotPullRequest(
                    title="Permissions per role",
                    additions=5,
                    deletions=1,
                    changed_files=1,
                    updated_at=_NOW - timedelta(minutes=3),
                    head_ref_oid="def456",
                    mergeable=SnapshotMergeability.CONFLICTING,
                    checks=None,
                ),
            ),
            SnapshotSlice(number="352", status=SnapshotSliceStatus.PENDING, title="Auditoria", pr_number=None),
        ],
        lessons=[],
    )


def _detail_text(app: LoopsApp) -> str:
    panel = app.query_one(PullRequestPanel)

    return f"{panel.border_title}\n" + "".join(_plain_text(line) for line in panel.query(Static))


class TestLoopsAppPullRequestPanel:
    def test_should_show_the_summary_of_the_pull_request_of_the_focused_slice(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _detail_text(app)

        with _one_alive_loop_with([_reviewed_story()]):
            text = asyncio.run(scenario())

        assert "Slice 1 · PR #61" in text
        assert "#61 Member roles" in text
        assert "+180 \u221222 · 7 files · checks ✓" in text
        assert "mergeable ✓ · updated 40s ago" in text

    def test_should_follow_the_focus_to_the_pull_request_of_another_slice(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "#62" in _detail_text(app))

                return _detail_text(app)

        with _one_alive_loop_with([_reviewed_story()]):
            text = asyncio.run(scenario())

        assert "Slice 2 · PR #62" in text
        assert "#62 Permissions per role" in text
        assert "checks —" in text
        assert "mergeable ✗ conflicts · updated 3m ago" in text

    def test_should_say_that_a_slice_without_pull_request_has_none_yet(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down", "down")
                await _wait_for(pilot, lambda: "no PR" in _detail_text(app))

                return _detail_text(app)

        with _one_alive_loop_with([_reviewed_story()]):
            text = asyncio.run(scenario())

        assert "Slice 3" in text
        assert "no PR yet" in text

    def test_should_hold_the_summary_in_a_pull_request_tab(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)):
                tabs = app.query_one(PullRequestPanel).query_one(Tabs)

                return [tab.label_text for tab in tabs.query("Tab").results(Tab)]

        with _one_alive_loop_with([_reviewed_story()]):
            labels = asyncio.run(scenario())

        assert labels == ["PR", "Diff", "Comments"]

    def test_should_expand_the_detail_with_enter_and_restore_the_columns_with_escape(self) -> None:
        async def scenario() -> tuple[bool, bool, str | None, bool]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down", "enter")
                expanded = app.screen.maximized is app.query_one(PullRequestPanel)
                await pilot.press("escape")

                return (
                    expanded,
                    app.screen.maximized is None,
                    app.query_one(SliceList).highlighted_slice,
                    app.query_one(SliceList).has_focus,
                )

        with _one_alive_loop_with([_reviewed_story()]):
            expanded, restored, highlighted, focused = asyncio.run(scenario())

        assert expanded is True
        assert restored is True
        assert highlighted == "351"
        assert focused is True

    def test_should_open_the_pull_request_of_the_focused_slice_with_o(self, monkeypatch: pytest.MonkeyPatch) -> None:
        opened: list[str] = []

        async def scenario() -> None:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down", "o")

        with _one_alive_loop_with([_reviewed_story()]):
            asyncio.run(scenario())

        assert opened == ["https://github.com/verify/alfa/pull/62"]


def _pull_request_detail(number: int, body: str, synced_seconds_ago: int) -> PullRequestDetail:
    return PullRequestDetail(
        number=number,
        body=body,
        updated_at=_NOW - timedelta(minutes=5),
        head_ref_oid="abc123",
        checks="success",
        synced_at=_NOW - timedelta(seconds=synced_seconds_ago),
        files=[],
        conversation=[],
        review=[],
    )


_BODY = "## Summary\n\nAddresses the [Spec](https://github.com/verify/alfa/issues/338)."
_LINKED_MARKDOWN = "Addresses the [Spec](https://github.com/verify/alfa/issues/338)."


class TestLoopsAppPullRequestBody:
    def test_should_show_the_body_of_the_pull_request_as_markdown(self) -> None:
        async def scenario() -> tuple[str, int]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                body = app.query_one(PullRequestBody)
                await _wait_for(pilot, lambda: len(body.query("MarkdownH2")) > 0)

                return body.source, len(body.query("MarkdownH2"))

        details = FakePullRequestDetails([_pull_request_detail(61, _BODY, synced_seconds_ago=40)])
        with _one_alive_loop_with([_reviewed_story()]), container.override(PullRequestDetails, details):
            source, headings = asyncio.run(scenario())

        assert source == _BODY
        assert headings == 1

    def test_should_not_open_a_link_of_the_body_the_user_clicks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        opened: list[str] = []

        async def scenario() -> None:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                body = app.query_one(PullRequestBody)
                await _wait_for(pilot, lambda: len(body.query("MarkdownParagraph")) > 0)
                paragraph = body.query("MarkdownParagraph").first()
                await pilot.click(paragraph, offset=_click_offset(paragraph, "/issues/338"))
                await pilot.pause()

        details = FakePullRequestDetails([_pull_request_detail(61, _BODY, synced_seconds_ago=40)])
        with _one_alive_loop_with([_reviewed_story()]), container.override(PullRequestDetails, details):
            asyncio.run(scenario())

        assert opened == []

    def test_should_show_how_long_ago_the_detail_was_synced(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _detail_text(app)

        details = FakePullRequestDetails([_pull_request_detail(61, _BODY, synced_seconds_ago=40)])
        with _one_alive_loop_with([_reviewed_story()]), container.override(PullRequestDetails, details):
            text = asyncio.run(scenario())

        assert "synced 40s ago" in text

    def test_should_wait_for_the_next_tick_and_keep_the_summary_when_the_detail_is_missing(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _detail_text(app)

        with _one_alive_loop_with([_reviewed_story()]):
            text = asyncio.run(scenario())

        assert "waiting for the next tick" in text
        assert "#61 Member roles" in text

    def test_should_mark_the_detail_as_unreadable_when_its_version_is_unknown(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _detail_text(app)

        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails(unreadable=[61])),
        ):
            text = asyncio.run(scenario())

        assert "unreadable detail" in text

    def test_should_not_wait_for_the_detail_of_a_merged_slice(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _detail_text(app)

        story = SnapshotStory(
            number="338",
            status=SnapshotStoryStatus.SLICED,
            title="Half merged story",
            slices=[
                SnapshotSlice(number="350", status=SnapshotSliceStatus.MERGED, title="Roles", pr_number="60"),
                SnapshotSlice(number="351", status=SnapshotSliceStatus.PR_OPEN, title="Permissions", pr_number="61"),
            ],
            lessons=[],
        )
        with _one_alive_loop_with([story]):
            text = asyncio.run(scenario())

        assert "PR #60" in text
        assert "waiting" not in text


def _commented_detail(
    number: int, conversation: list[PullRequestComment], review: list[PullRequestComment]
) -> PullRequestDetail:
    return PullRequestDetail(
        number=number,
        body=_BODY,
        updated_at=_NOW - timedelta(minutes=5),
        head_ref_oid="abc123",
        checks="success",
        synced_at=_NOW - timedelta(seconds=40),
        files=[],
        conversation=conversation,
        review=review,
    )


_REVIEW_SUMMARY = PullRequestComment(
    author="grooveloop-reviewer", body="Verdict: **ok**", created_at=_NOW - timedelta(minutes=30)
)
_INLINE_COMMENT = PullRequestComment(
    author="octocat",
    body="Rename this `variable`",
    created_at=_NOW - timedelta(minutes=20),
    path="src/roles.py",
    line=42,
    diff_hunk="@@ -40,3 +40,3 @@\n-    old = 1\n+    new = 1",
)
_HUMAN_DIRECTIVE = PullRequestComment(
    author=None, body="/grooveloop-implement", created_at=_NOW - timedelta(minutes=10)
)


def _comments_text(app: LoopsApp) -> str:
    comments = app.query_one(PullRequestComments)

    return "\n".join(_plain_text(static) for static in comments.query(Static))


class TestLoopsAppPullRequestComments:
    def test_should_not_open_a_link_of_a_comment_the_user_clicks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        opened: list[str] = []

        async def scenario() -> None:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                await pilot.click(_pull_request_tab(app, "Comments"))
                comments = app.query_one(PullRequestComments)
                await _wait_for(pilot, lambda: len(comments.query("MarkdownParagraph")) > 0)
                paragraph = comments.query("MarkdownParagraph").first()
                await pilot.click(paragraph, offset=_click_offset(paragraph, "/issues/338"))
                await pilot.pause()

        linked = PullRequestComment(
            author="grooveloop-reviewer", body=_LINKED_MARKDOWN, created_at=_NOW - timedelta(minutes=30)
        )
        detail = _commented_detail(61, [linked], [])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            asyncio.run(scenario())

        assert opened == []

    def test_should_count_the_comments_in_the_label_of_the_tab(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                tabs = app.query_one(PullRequestPanel).query_one(Tabs)

                return [tab.label_text for tab in tabs.query("Tab").results(Tab)]

        detail = _commented_detail(61, [_REVIEW_SUMMARY, _HUMAN_DIRECTIVE], [_INLINE_COMMENT])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            labels = asyncio.run(scenario())

        assert labels == ["PR", "Diff", "Comments 3"]

    def test_should_mix_conversation_and_inline_comments_in_chronological_order(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _comments_text(app)

        detail = _commented_detail(61, [_HUMAN_DIRECTIVE, _REVIEW_SUMMARY], [_INLINE_COMMENT])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            text = asyncio.run(scenario())

        assert text.index("grooveloop-reviewer") < text.index("octocat") < text.index("unknown")

    def test_should_show_the_file_line_and_hunk_of_an_inline_comment(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _comments_text(app)

        detail = _commented_detail(61, [], [_INLINE_COMMENT])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            text = asyncio.run(scenario())

        assert "octocat · 20m ago · src/roles.py:42" in text
        assert "+    new = 1" in text

    def test_should_show_the_body_of_each_comment_as_markdown(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return [body.source for body in app.query_one(PullRequestComments).query(Markdown).results(Markdown)]

        detail = _commented_detail(61, [_REVIEW_SUMMARY], [_INLINE_COMMENT])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            sources = asyncio.run(scenario())

        assert sources == ["Verdict: **ok**", "Rename this `variable`"]

    def test_should_say_that_a_pull_request_without_comments_has_none(self) -> None:
        async def scenario() -> tuple[str, list[str]]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                tabs = app.query_one(PullRequestPanel).query_one(Tabs)

                return _comments_text(app), [tab.label_text for tab in tabs.query("Tab").results(Tab)]

        detail = _commented_detail(61, [], [])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            text, labels = asyncio.run(scenario())

        assert "no comments" in text
        assert labels == ["PR", "Diff", "Comments 0"]

    def test_should_keep_the_comments_widgets_across_refreshes(self) -> None:
        async def scenario() -> bool:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                first = app.query_one(PullRequestComments).query_one(Markdown)
                await _refresh(app, pilot)

                return app.query_one(PullRequestComments).query_one(Markdown) is first

        detail = _commented_detail(61, [_REVIEW_SUMMARY], [])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            kept = asyncio.run(scenario())

        assert kept is True


def _detail_with_files(number: int, files: list[PullRequestFile]) -> PullRequestDetail:
    return PullRequestDetail(
        number=number,
        body=_BODY,
        updated_at=_NOW - timedelta(minutes=5),
        head_ref_oid="abc123",
        checks="success",
        synced_at=_NOW - timedelta(seconds=40),
        files=files,
        conversation=[],
        review=[],
    )


_MODIFIED_FILE = PullRequestFile(
    filename="src/roles.py",
    status="modified",
    additions=12,
    deletions=3,
    patch="@@ -40,3 +40,3 @@\n context = 0\n-    old = 1\n+    new = 1",
)
_ADDED_FILE = PullRequestFile(
    filename="src/permissions.py", status="added", additions=4, deletions=0, patch="@@ -0,0 +1,1 @@\n+allowed = True"
)
_BINARY_FILE = PullRequestFile(filename="docs/logo.png", status="added", additions=0, deletions=0, patch=None)


def _file_prompts(app: LoopsApp) -> list[str]:
    files = app.query_one(PullRequestDiff).query_one(OptionList)

    return [_render_plain(files.get_option_at_index(index).prompt) for index in range(files.option_count)]


def _patch_text(app: LoopsApp) -> str:
    return _plain_text(app.query_one(PullRequestPatch))


def _line_color(renderable: Any, fragment: str) -> str | None:
    console = Console(width=120, color_system="truecolor")
    segments = console.render(renderable, console.options)

    return next((str(segment.style.color) for segment in segments if fragment in segment.text and segment.style), None)


class TestLoopsAppPullRequestDiff:
    def test_should_list_each_file_of_the_pull_request_with_its_additions_and_deletions(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _file_prompts(app)

        detail = _detail_with_files(61, [_MODIFIED_FILE, _ADDED_FILE])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            prompts = asyncio.run(scenario())

        assert "src/roles.py" in prompts[0]
        assert "modified" in prompts[0]
        assert "+12 \u22123" in prompts[0]
        assert "src/permissions.py" in prompts[1]
        assert "+4 \u22120" in prompts[1]

    def test_should_show_the_patch_of_the_chosen_file(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                app.query_one(PullRequestDiff).query_one(OptionList).highlighted = 1
                await _wait_for(pilot, lambda: "allowed" in _patch_text(app))

                return _patch_text(app)

        detail = _detail_with_files(61, [_MODIFIED_FILE, _ADDED_FILE])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            text = asyncio.run(scenario())

        assert "+allowed = True" in text
        assert "old = 1" not in text

    def test_should_paint_added_and_deleted_lines_in_different_colors(self) -> None:
        async def scenario() -> Any:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return app.query_one(PullRequestPatch).content

        detail = _detail_with_files(61, [_MODIFIED_FILE])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            patch = asyncio.run(scenario())

        added, deleted = _line_color(patch, "new = 1"), _line_color(patch, "old = 1")
        assert added is not None
        assert deleted is not None
        assert added != deleted

    def test_should_warn_instead_of_the_diff_when_a_file_has_no_patch(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _patch_text(app)

        detail = _detail_with_files(61, [_BINARY_FILE])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            text = asyncio.run(scenario())

        assert "GitHub did not send the patch" in text
        assert "press o to open the PR" in text

    def test_should_keep_the_chosen_file_across_refreshes(self) -> None:
        async def scenario() -> tuple[int | None, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                files = app.query_one(PullRequestDiff).query_one(OptionList)
                files.highlighted = 1
                await _refresh(app, pilot)

                return files.highlighted, _patch_text(app)

        detail = _detail_with_files(61, [_MODIFIED_FILE, _ADDED_FILE])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            highlighted, text = asyncio.run(scenario())

        assert highlighted == 1
        assert "+allowed = True" in text

    def test_should_expand_the_detail_with_enter_from_the_list_of_files(self) -> None:
        async def scenario() -> tuple[bool, bool]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                app.query_one(PullRequestPanel).query_one(TabbedContent).active = "pull-request-diff"
                files = app.query_one(PullRequestFiles)
                files.focus()
                await pilot.press("enter")
                expanded = app.screen.maximized is app.query_one(PullRequestPanel)
                await pilot.press("escape")

                return expanded, files.has_focus

        detail = _detail_with_files(61, [_MODIFIED_FILE, _ADDED_FILE])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            expanded, focused = asyncio.run(scenario())

        assert expanded is True
        assert focused is True


class TestLoopsAppPullRequestTabs:
    @pytest.mark.parametrize("label", ["PR", "Comments"])
    def test_should_keep_the_tab_chosen_after_a_file_of_the_diff_across_refreshes(self, label: str) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                await _choose_second_file_of_the_diff(app, pilot)
                await pilot.click(_pull_request_tab(app, label))
                actives = []
                for _ in range(2):
                    await _refresh(app, pilot)
                    actives.append(_active_pull_request_tab(app))

                return actives

        detail = _detail_with_files(61, [_MODIFIED_FILE, _ADDED_FILE])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            actives = asyncio.run(scenario())

        assert actives == [label, label]

    def test_should_keep_the_tab_chosen_when_the_focus_goes_to_a_run_of_the_slice_and_back(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                await _choose_second_file_of_the_diff(app, pilot)
                await pilot.click(_pull_request_tab(app, "PR"))
                app.query_one(SliceList).focus()
                await pilot.press("down", "up")
                await _refresh(app, pilot)

                return _active_pull_request_tab(app)

        detail = _detail_with_files(61, [_MODIFIED_FILE, _ADDED_FILE])
        with (
            _reviewed_story_with_a_review_run(),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            active = asyncio.run(scenario())

        assert active == "PR"

    def test_should_show_the_chosen_file_when_going_back_to_the_diff(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                await _choose_second_file_of_the_diff(app, pilot)
                await pilot.click(_pull_request_tab(app, "PR"))
                await _refresh(app, pilot)
                await pilot.click(_pull_request_tab(app, "Diff"))
                await pilot.pause()

                return _patch_text(app)

        detail = _detail_with_files(61, [_MODIFIED_FILE, _ADDED_FILE])
        with (
            _one_alive_loop_with([_reviewed_story()]),
            container.override(PullRequestDetails, FakePullRequestDetails([detail])),
        ):
            text = asyncio.run(scenario())

        assert "+allowed = True" in text


async def _choose_second_file_of_the_diff(app: LoopsApp, pilot: Pilot[int]) -> None:
    await pilot.click(_pull_request_tab(app, "Diff"))
    await pilot.pause()
    await pilot.click(app.query_one(PullRequestFiles), offset=(2, 0))
    await pilot.press("down")
    await pilot.pause()


def _pull_request_tab(app: LoopsApp, label: str) -> Tab:
    tabs = app.query_one(PullRequestPanel).query(Tab)

    return next(tab for tab in tabs if tab.label.plain.split(" ")[0] == label)


def _active_pull_request_tab(app: LoopsApp) -> str:
    tabbed_content = app.query_one(PullRequestPanel).query_one(TabbedContent)

    return tabbed_content.get_tab(tabbed_content.active).label.plain.split(" ")[0]


_REVIEW_RUN_ID = "5cf547af-7d1e-4f1b-9d4e-3a0c1b2d4e5f"
_REVIEW_COST_SHARES = [
    CostShare(TokenClass.INPUT, 1_000, 0.0100),
    CostShare(TokenClass.CACHE_READ, 450_000, 0.1968),
    CostShare(TokenClass.CACHE_WRITE, 31_000, 0.1558),
    CostShare(TokenClass.OUTPUT, 4_000, 0.0474),
]


def _review_run(
    last_event_at: datetime = _NOW - timedelta(seconds=8),
    outcome: AgentOutcome = AgentOutcome.RUNNING,
    cause: AgentRunCause = AgentRunCause.EMPTY,
) -> AgentSession:
    return AgentSession(
        slice_id=SliceId("350"),
        outcome=outcome,
        task_type=AgentTaskType.REVIEW_SLICE,
        engine="claude",
        run_id=_REVIEW_RUN_ID,
        started_at=_NOW - timedelta(seconds=134),
        has_log=True,
        elapsed_seconds=134.0,
        total_cost_usd=0.41,
        models=[
            ModelUsage("claude-opus-5-5", 800, 3_000, 400_000, 30_000, 0.36),
            ModelUsage("claude-haiku-4-5", 200, 1_000, 50_000, 1_000, 0.05),
        ],
        launch_model="claude-opus-5-5",
        last_event_at=last_event_at,
        last_action="Bash: make test",
        turns=9,
        subagents=1,
        skills=["backend-best-practices"],
        tools=[ToolTally("Bash", 6), ToolTally("Read", 2)],
        cost_split=CostSplit(basis=CostBasis.DERIVED, shares=_REVIEW_COST_SHARES),
        profile="reviewer",
        cause=cause,
    )


def _run_detail_text(app: LoopsApp) -> str:
    panel = app.query_one(RunPanel)

    return f"{panel.border_title}\n" + "".join(_plain_text(line) for line in panel.query(Static))


@contextmanager
def _reviewed_story_with_a_review_run() -> Iterator[None]:
    sessions = FakeAgentSessionRepository({("verify/alfa", "350"): [_review_run()]})
    with _one_alive_loop_with([_reviewed_story()]), container.override(AgentSessionRepository, sessions):
        yield


def _unstarted_review_run() -> AgentSession:
    return AgentSession(
        slice_id=SliceId("350"),
        outcome=AgentOutcome.RUNNING,
        task_type=AgentTaskType.REVIEW_SLICE,
        engine="claude",
        run_id=_REVIEW_RUN_ID,
        started_at=_NOW - timedelta(minutes=10),
        has_log=False,
        elapsed_seconds=600.0,
        profile="reviewer",
    )


@contextmanager
def _reviewed_story_with_an_unstarted_review_run() -> Iterator[None]:
    sessions = FakeAgentSessionRepository({("verify/alfa", "350"): [_unstarted_review_run()]})
    with _one_alive_loop_with([_reviewed_story()]), container.override(AgentSessionRepository, sessions):
        yield


class TestLoopsAppRunPanel:
    def test_should_show_the_detail_of_the_run_the_user_reaches_with_the_cursor_keys(self) -> None:
        async def scenario() -> tuple[bool, bool, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: app.query_one(RunPanel).display)

                return app.query_one(RunPanel).display, app.query_one(PullRequestPanel).display, _run_detail_text(app)

        with _reviewed_story_with_a_review_run():
            run_shown, pull_request_shown, text = asyncio.run(scenario())

        assert run_shown is True
        assert pull_request_shown is False
        assert "Run review_slice · slice 1" in text
        assert "review_slice · reviewer · ▶ 2m14s" in text
        assert "run 5cf547af · claude" in text

    def test_should_go_back_to_the_pull_request_when_the_focus_returns_to_its_slice(self) -> None:
        async def scenario() -> tuple[bool, bool, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down", "up")
                await pilot.pause()

                return app.query_one(RunPanel).display, app.query_one(PullRequestPanel).display, _detail_text(app)

        with _reviewed_story_with_a_review_run():
            run_shown, pull_request_shown, text = asyncio.run(scenario())

        assert run_shown is False
        assert pull_request_shown is True
        assert "#61 Member roles" in text

    def test_should_show_the_detail_of_the_run_the_user_clicks(self) -> None:
        async def scenario() -> tuple[str | None, bool]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                await pilot.click(app.query_one(f"#run-{_REVIEW_RUN_ID}", SessionRow), offset=(1, 0))
                await pilot.pause()

                return app.query_one(SliceList).highlighted_run, app.query_one(RunPanel).display

        with _reviewed_story_with_a_review_run():
            highlighted, shown = asyncio.run(scenario())

        assert highlighted == _REVIEW_RUN_ID
        assert shown is True

    def test_should_show_the_cause_of_an_interrupted_run_next_to_its_duration(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "cost" in _run_detail_text(app))

                return _run_detail_text(app)

        with _reviewed_story_with_a_review_run_that(AgentOutcome.INTERRUPTED, AgentRunCause.OVERLOADED):
            text = asyncio.run(scenario())

        assert "↯ 2m14s · overloaded" in text

    def test_should_show_an_unstarted_run_without_treating_it_as_running(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: app.query_one(RunPanel).display)

                return _run_detail_text(app)

        with _reviewed_story_with_an_unstarted_review_run():
            text = asyncio.run(scenario())

        assert "review_slice · reviewer · · 10m00s" in text
        assert "▶" not in text
        assert "LIVE" not in text
        assert "silent" not in text

    def test_should_split_the_cost_by_token_class_adding_up_to_the_total(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "cost" in _run_detail_text(app))

                return _run_detail_text(app)

        with _reviewed_story_with_a_review_run():
            text = asyncio.run(scenario())

        shares = [float(amount) for amount in re.findall(r"(?:input|cache read|cache write|output) \$(\d+\.\d+)", text)]
        assert "cost $0.4100" in text
        assert len(shares) == 4
        assert sum(shares) == pytest.approx(0.41, abs=0.0005)

    def test_should_give_each_model_of_the_run_its_own_line(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "claude-haiku" in _run_detail_text(app))

                return _run_detail_text(app).splitlines()

        with _reviewed_story_with_a_review_run():
            lines = asyncio.run(scenario())

        assert [line.strip() for line in lines if line.strip().startswith("claude-")] == [
            "claude-opus-5-5 $0.3600 ↑430.8K · 92.9% cached · ↓3.0K",
            "claude-haiku-4-5 $0.0500 ↑51.2K · 97.7% cached · ↓1.0K",
        ]

    def test_should_show_the_tokens_turns_tools_skills_and_last_action_of_the_run(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "turns" in _run_detail_text(app))

                return _run_detail_text(app)

        with _reviewed_story_with_a_review_run():
            text = asyncio.run(scenario())

        assert "tokens ↑482.0K · 93.4% cached · ↓4.0K" in text
        assert "turns 9 · subagents 1" in text
        assert "tools Bash 6 · Read 2" in text
        assert "skills backend-best-practices" in text
        assert "last ↳ Bash: make test · silent 8s" in text

    def test_should_grow_the_silence_of_a_running_run_between_refreshes_keeping_the_focus(self) -> None:
        clock = clock_at(_NOW)

        async def scenario() -> tuple[str, str, str | None]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "silent 8s" in _run_detail_text(app))
                before = _run_detail_text(app)
                clock.now.return_value = _NOW + timedelta(seconds=30)
                await _refresh(app, pilot)

                return before, _run_detail_text(app), app.query_one(SliceList).highlighted_run

        with _reviewed_story_with_a_review_run(), container.override(Clock, clock):
            before, after, highlighted = asyncio.run(scenario())

        assert "silent 8s" in before
        assert "silent 38s" in after
        assert highlighted == _REVIEW_RUN_ID

    def test_should_expand_the_detail_of_the_focused_run_with_enter(self) -> None:
        async def scenario() -> bool:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: app.query_one(RunPanel).display)
                await pilot.press("enter")

                return app.screen.maximized is app.query_one(RunPanel)

        with _reviewed_story_with_a_review_run():
            expanded = asyncio.run(scenario())

        assert expanded is True


_READ_ACTION = AgentLogAction("Read · src/roles.py", "toolu_1")
_TEST_ACTION = AgentLogAction("Bash · make test", "toolu_2")
_EDIT_ACTION = AgentLogAction("Edit · src/roles.py", "toolu_3")


def _log_text(app: LoopsApp) -> str:
    return _plain_text(app.query_one(RunLog))


async def _open_the_log_of_the_review_run(pilot: Pilot[int], app: LoopsApp) -> None:
    await pilot.press("tab", "down")
    await _wait_for(pilot, lambda: app.query_one(RunPanel).display)
    app.query_one(RunPanel).query_one(TabbedContent).active = "run-log"
    await pilot.pause()


@contextmanager
def _reviewed_story_with_a_review_run_that(
    outcome: AgentOutcome, cause: AgentRunCause = AgentRunCause.EMPTY
) -> Iterator[None]:
    sessions = FakeAgentSessionRepository({("verify/alfa", "350"): [_review_run(outcome=outcome, cause=cause)]})
    with _one_alive_loop_with([_reviewed_story()]), container.override(AgentSessionRepository, sessions):
        yield


class TestLoopsAppRunLog:
    def test_should_show_one_line_per_action_in_the_order_of_the_log_and_the_result_at_the_end(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_the_log_of_the_review_run(pilot, app)
                await _wait_for(pilot, lambda: "Edit" in _log_text(app))

                return [line.strip() for line in _log_text(app).splitlines() if line.strip()]

        logs = FakeAgentRunLogs({_REVIEW_RUN_ID: [_READ_ACTION, _TEST_ACTION, _EDIT_ACTION]})
        with _reviewed_story_with_a_review_run_that(AgentOutcome.SUCCEEDED), container.override(AgentRunLogs, logs):
            lines = asyncio.run(scenario())

        assert lines == [
            "↳ Read · src/roles.py",
            "↳ Bash · make test",
            "↳ Edit · src/roles.py",
            "✓ result: done",
        ]

    def test_should_end_the_log_of_an_interrupted_run_with_its_cause(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_the_log_of_the_review_run(pilot, app)
                await _wait_for(pilot, lambda: "result" in _log_text(app))

                return _log_text(app)

        logs = FakeAgentRunLogs({_REVIEW_RUN_ID: [_READ_ACTION]})
        interrupted = _reviewed_story_with_a_review_run_that(AgentOutcome.INTERRUPTED, AgentRunCause.OVERLOADED)
        with interrupted, container.override(AgentRunLogs, logs):
            text = asyncio.run(scenario())

        assert "↯ result: interrupted · overloaded" in text

    def test_should_show_once_an_action_the_streaming_of_claude_repeats(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_the_log_of_the_review_run(pilot, app)
                await _wait_for(pilot, lambda: "Edit" in _log_text(app))

                return _log_text(app)

        logs = FakeAgentRunLogs({_REVIEW_RUN_ID: [_READ_ACTION, _READ_ACTION, _EDIT_ACTION]})
        with _reviewed_story_with_a_review_run(), container.override(AgentRunLogs, logs):
            text = asyncio.run(scenario())

        assert text.count("Read · src/roles.py") == 1

    def test_should_not_read_the_log_until_its_tab_is_opened(self) -> None:
        logs = FakeAgentRunLogs({_REVIEW_RUN_ID: [_READ_ACTION]})

        async def scenario() -> list[tuple[str, int]]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: app.query_one(RunPanel).display)

                return list(logs.reads)

        with _reviewed_story_with_a_review_run(), container.override(AgentRunLogs, logs):
            reads = asyncio.run(scenario())

        assert reads == []

    def test_should_add_a_new_action_of_a_running_run_without_reading_the_log_from_the_start(self) -> None:
        logs = FakeAgentRunLogs({_REVIEW_RUN_ID: [_READ_ACTION]})

        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_the_log_of_the_review_run(pilot, app)
                await _wait_for(pilot, lambda: "Read" in _log_text(app))
                logs.append(_REVIEW_RUN_ID, _TEST_ACTION)
                await _refresh(app, pilot)

                return _log_text(app)

        with _reviewed_story_with_a_review_run(), container.override(AgentRunLogs, logs):
            text = asyncio.run(scenario())

        assert "↳ Read · src/roles.py" in text
        assert "↳ Bash · make test" in text
        first_read, *later_reads = logs.reads
        assert first_read == (_REVIEW_RUN_ID, 0)
        assert len(later_reads) > 0
        assert all(offset > 0 for _, offset in later_reads)

    def test_should_warn_instead_of_the_timeline_when_the_run_has_no_log(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_the_log_of_the_review_run(pilot, app)
                await _wait_for(pilot, lambda: "agent.log" in _log_text(app))

                return _log_text(app)

        with _reviewed_story_with_an_unstarted_review_run(), container.override(AgentRunLogs, FakeAgentRunLogs()):
            text = asyncio.run(scenario())

        assert "no agent.log" in text
        assert "result" not in text


def _row_updates(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    updated: list[str] = []
    update = ListRow.update

    def counted(row: ListRow, *args: Any, **kwargs: Any) -> None:
        updated.append(str(row.id))
        update(row, *args, **kwargs)

    monkeypatch.setattr(ListRow, "update", counted)

    return updated


class TestLoopsAppSliceListRepaint:
    def test_should_update_only_the_two_rows_the_focus_leaves_and_reaches(
        self, one_alive_loop_with_two_stories: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        updated = _row_updates(monkeypatch)

        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab")
                await pilot.pause()
                updated.clear()
                await pilot.press("down")
                await pilot.pause()

                return list(updated)

        assert sorted(asyncio.run(scenario())) == ["slice-350", "slice-351"]

    def test_should_leave_untouched_the_row_that_keeps_its_mark_when_the_focus_moves(
        self, one_alive_loop_with_a_dependency_chain: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        updated = _row_updates(monkeypatch)

        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab")
                await pilot.pause()
                updated.clear()
                await pilot.press("down")
                await pilot.pause()

                return list(updated)

        assert sorted(asyncio.run(scenario())) == ["slice-350", "slice-351"]

    def test_should_update_no_row_on_a_refresh_without_changes(
        self, one_alive_loop_with_two_stories: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        updated = _row_updates(monkeypatch)

        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await pilot.pause()
                updated.clear()
                await _refresh(app, pilot)

                return list(updated)

        assert asyncio.run(scenario()) == []

    def test_should_update_only_the_run_whose_silence_grows_on_a_refresh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = clock_at(_NOW)
        updated = _row_updates(monkeypatch)

        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab")
                await pilot.pause()
                updated.clear()
                clock.now.return_value = _NOW + timedelta(seconds=30)
                await _refresh(app, pilot)

                return list(updated)

        with _reviewed_story_with_a_review_run(), container.override(Clock, clock):
            updated_rows = asyncio.run(scenario())

        assert set(updated_rows) == {f"run-{_REVIEW_RUN_ID}"}


def _journal_entry(kind: EntryKind, author: str, body: str, minutes_ago: int, story_id: str = "338") -> JournalEntry:
    return JournalEntryMother.create(
        repo="verify/alfa",
        story_id=story_id,
        kind=kind,
        author=author,
        body=body,
        written_at=_NOW - timedelta(minutes=minutes_ago),
    )


_DECISION = _journal_entry(EntryKind.DECISION, "human", "Slice 11 waits.\n\nFor the **soft delete**.", 20)
_CONSTRAINT = _journal_entry(EntryKind.CONSTRAINT, "reviewer", "The `urls.py` files end up included twice.", 6)


@contextmanager
def _journal_with(entries: list[JournalEntry]) -> Iterator[FakeJournalEntryRepository]:
    repository = FakeJournalEntryRepository()
    repository.saved.extend(entries)
    with container.override(JournalEntryRepository, repository):
        yield repository


def _story_tab_labels(app: LoopsApp) -> list[str]:
    tabs = app.query_one("#story-tabs", TabbedContent).query_one(Tabs)

    return [tab.label_text for tab in tabs.query("Tab").results(Tab)]


def _journal_sources(app: LoopsApp) -> list[str]:
    return [
        body.source
        for block in app.query_one(StoryJournal).query(JournalEntryBlock).results(JournalEntryBlock)
        if block.display
        for body in block.query(Markdown).results(Markdown)
    ]


def _journal_headers(app: LoopsApp) -> list[str]:
    journal = app.query_one(StoryJournal)

    return [_plain_text(header).strip() for header in journal.query(JournalEntryHeader).results(JournalEntryHeader)]


async def _open_journal(pilot: Pilot[int]) -> None:
    await pilot.pause()
    await pilot.click("#story-tabs Tab#--content-tab-journal")
    await pilot.pause()


class TestLoopsAppStoryJournal:
    def test_should_not_open_a_link_of_an_entry_the_user_clicks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        opened: list[str] = []

        async def scenario() -> None:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_journal(pilot)
                journal = app.query_one(StoryJournal)
                await _wait_for(pilot, lambda: len(journal.query("MarkdownParagraph")) > 0)
                paragraph = journal.query("MarkdownParagraph").first()
                await pilot.click(paragraph, offset=_click_offset(paragraph, "/issues/338"))
                await pilot.pause()

        linked = _journal_entry(EntryKind.DECISION, "human", _LINKED_MARKDOWN, 20)
        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with([linked, _CONSTRAINT]):
            asyncio.run(scenario())

        assert opened == []

    def test_should_count_the_entries_in_the_label_of_the_tab(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _story_tab_labels(app)

        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with([_DECISION, _CONSTRAINT]):
            labels = asyncio.run(scenario())

        assert labels == ["Slices", "Spec", "Journal 2"]

    def test_should_show_each_entry_with_its_age_kind_and_author_from_the_oldest(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_journal(pilot)

                return _journal_headers(app)

        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with([_DECISION, _CONSTRAINT]):
            headers = asyncio.run(scenario())

        assert headers == ["20m ago · decision · human", "6m ago · constraint · reviewer"]

    def test_should_show_the_whole_body_of_each_entry_as_markdown(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_journal(pilot)

                return _journal_sources(app)

        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with([_DECISION, _CONSTRAINT]):
            sources = asyncio.run(scenario())

        assert sources == [_DECISION.body, _CONSTRAINT.body]

    def test_should_show_the_latest_entry_when_the_user_opens_the_tab(self) -> None:
        entries = [
            _journal_entry(EntryKind.FINDING, "developer", f"finding {minutes}\n\n" + "line\n\n" * 6, minutes)
            for minutes in range(30, 0, -1)
        ]

        async def scenario() -> tuple[float, float]:
            app = _app()
            async with app.run_test(size=_SHORT_SCREEN) as pilot:
                await _open_journal(pilot)
                scroll = app.query_one(JournalEntries)
                await _wait_for(pilot, lambda: scroll.max_scroll_y > 0 and scroll.scroll_y == scroll.max_scroll_y)

                return scroll.scroll_y, scroll.max_scroll_y

        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with(entries):
            scroll_y, max_scroll_y = asyncio.run(scenario())

        assert max_scroll_y > 0
        assert scroll_y == max_scroll_y

    def test_should_show_an_entry_written_after_the_start_on_the_next_refresh(self) -> None:
        async def scenario(repository: FakeJournalEntryRepository) -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_journal(pilot)
                repository.saved.append(_CONSTRAINT)
                await _refresh(app, pilot)

                return _journal_sources(app)

        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with([_DECISION]) as repository:
            sources = asyncio.run(scenario(repository))

        assert sources == [_DECISION.body, _CONSTRAINT.body]

    def test_should_keep_the_entries_painted_while_no_new_entry_arrives(self) -> None:
        async def scenario() -> bool:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_journal(pilot)
                before = list(app.query_one(StoryJournal).query(Markdown).results(Markdown))
                await _refresh(app, pilot)
                after = list(app.query_one(StoryJournal).query(Markdown).results(Markdown))

                return len(before) == 2 and all(one is other for one, other in zip(before, after, strict=True))

        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with([_DECISION, _CONSTRAINT]):
            kept = asyncio.run(scenario())

        assert kept is True

    def test_should_hide_the_entries_of_the_other_kinds_when_the_user_clicks_a_kind(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_journal(pilot)
                journal_filter = app.query_one(JournalFilter)
                await pilot.click(journal_filter, offset=_click_offset(journal_filter, "constraint"))
                await pilot.pause()

                return _journal_sources(app)

        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with([_DECISION, _CONSTRAINT]):
            sources = asyncio.run(scenario())

        assert sources == [_CONSTRAINT.body]

    def test_should_move_through_the_kinds_with_the_filter_key(self) -> None:
        async def scenario() -> list[list[str]]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_journal(pilot)
                seen = []
                for _ in range(5):
                    await pilot.press("f")
                    await pilot.pause()
                    seen.append(_journal_sources(app))

                return seen

        with _one_alive_loop_with([_story("Alfa story", 1)]), _journal_with([_DECISION, _CONSTRAINT]):
            seen = asyncio.run(scenario())

        assert seen == [[_CONSTRAINT.body], [], [_DECISION.body], [], [_DECISION.body, _CONSTRAINT.body]]


_SPEC = "## Design\n\nThe Story asks for **two** tabs.\n\n```python\nprint('spec')\n```\n"


@contextmanager
def _specs_with(specs: dict[int, str]) -> Iterator[FakeStorySpecs]:
    story_specs = FakeStorySpecs(specs)
    with container.override(StorySpecs, story_specs):
        yield story_specs


def _spec_body(app: LoopsApp) -> Markdown:
    return app.query_one(StorySpec).query_one(Markdown)


async def _open_spec(pilot: Pilot[int]) -> None:
    await pilot.pause()
    await pilot.click("#story-tabs Tab#--content-tab-spec")
    await pilot.pause()


class TestLoopsAppStorySpec:
    def test_should_not_open_a_link_of_the_spec_the_user_clicks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        opened: list[str] = []

        async def scenario() -> None:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_spec(pilot)
                body = _spec_body(app)
                await _wait_for(pilot, lambda: len(body.query("MarkdownParagraph")) > 0)
                paragraph = body.query("MarkdownParagraph").first()
                await pilot.click(paragraph, offset=_click_offset(paragraph, "/issues/338"))
                await pilot.pause()

        with _one_alive_loop_with([_story("Alfa story", 1)]), _specs_with({338: _LINKED_MARKDOWN}):
            asyncio.run(scenario())

        assert opened == []

    def test_should_show_the_spec_of_the_story_as_markdown(self) -> None:
        async def scenario() -> tuple[str, int, int]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_spec(pilot)
                body = _spec_body(app)

                return body.source, len(body.query("MarkdownH2")), len(body.query(MarkdownFence))

        with _one_alive_loop_with([_story("Alfa story", 1)]), _specs_with({338: _SPEC}):
            source, headings, fences = asyncio.run(scenario())

        assert source == _SPEC
        assert headings == 1
        assert fences == 1

    def test_should_wait_for_the_next_tick_when_the_story_has_no_spec_yet(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_spec(pilot)

                return _spec_body(app).source

        with _one_alive_loop_with([_story("Alfa story", 1)]), _specs_with({}):
            source = asyncio.run(scenario())

        assert source == "waiting for the next tick"

    def test_should_show_the_edited_spec_on_the_next_refresh(self) -> None:
        async def scenario(story_specs: FakeStorySpecs) -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_spec(pilot)
                story_specs.publish("verify/alfa", 338, _SPEC)
                await _refresh(app, pilot)

                return _spec_body(app).source

        with _one_alive_loop_with([_story("Alfa story", 1)]), _specs_with({338: "before"}) as story_specs:
            source = asyncio.run(scenario(story_specs))

        assert source == _SPEC

    def test_should_keep_the_spec_painted_while_its_file_does_not_change(self) -> None:
        async def scenario() -> bool:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_spec(pilot)
                before = list(_spec_body(app).children)
                await _refresh(app, pilot)
                after = list(_spec_body(app).children)

                return len(before) > 0 and all(one is other for one, other in zip(before, after, strict=True))

        with _one_alive_loop_with([_story("Alfa story", 1)]), _specs_with({338: _SPEC}):
            kept = asyncio.run(scenario())

        assert kept is True

    def test_should_scroll_the_spec_with_the_keyboard_as_soon_as_the_tab_opens(self) -> None:
        tall_spec = "".join(f"## Section {section}\n\nline\n\n" for section in range(30))

        async def scenario() -> float:
            app = _app()
            async with app.run_test(size=_SHORT_SCREEN) as pilot:
                await _open_spec(pilot)
                await pilot.press("end")
                await pilot.pause()

                return app.query_one(StorySpec).scroll_y

        with _one_alive_loop_with([_story("Alfa story", 1)]), _specs_with({338: tall_spec}):
            scroll_y = asyncio.run(scenario())

        assert scroll_y > 0


async def _open_slices(pilot: Pilot[int]) -> None:
    await pilot.click("#story-tabs Tab#--content-tab-slices")
    await pilot.pause()


class TestLoopsAppColumns:
    @pytest.mark.parametrize("screen_width", [160, 220])
    def test_should_give_the_center_and_the_detail_the_same_width_with_the_slices_tab(self, screen_width: int) -> None:
        async def scenario() -> tuple[int, int]:
            app = _app()
            async with app.run_test(size=(screen_width, 40)) as pilot:
                await pilot.pause()

                return app.query_one("#center").region.width, app.query_one(PullRequestPanel).region.width

        with _one_alive_loop_with([_reviewed_story()]):
            center, detail = asyncio.run(scenario())

        assert abs(center - detail) <= 1

    def test_should_keep_the_center_at_its_minimum_width_and_narrow_the_detail_on_a_narrow_screen(self) -> None:
        async def scenario() -> tuple[int, int]:
            app = _app()
            async with app.run_test(size=(130, 40)) as pilot:
                await pilot.pause()

                return app.query_one("#center").region.width, app.query_one(PullRequestPanel).region.width

        with _one_alive_loop_with([_reviewed_story()]):
            center, detail = asyncio.run(scenario())

        assert center == CENTER_MIN_WIDTH
        assert 0 < detail < center

    @pytest.mark.parametrize("pane", ["spec", "journal"])
    def test_should_hide_the_detail_and_widen_the_center_with_the_spec_or_the_journal_tab(self, pane: str) -> None:
        async def scenario() -> tuple[bool, bool, int, int]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                detail_right = app.query_one(PullRequestPanel).region.right
                await pilot.click(f"#story-tabs Tab#--content-tab-{pane}")
                await pilot.pause()

                return (
                    app.query_one(PullRequestPanel).display,
                    app.query_one(RunPanel).display,
                    app.query_one("#center").region.right,
                    detail_right,
                )

        with _one_alive_loop_with([_reviewed_story()]):
            pull_request_shown, run_shown, center_right, detail_right = asyncio.run(scenario())

        assert pull_request_shown is False
        assert run_shown is False
        assert center_right == detail_right

    def test_should_show_the_detail_of_the_focused_row_again_when_the_slices_tab_comes_back(self) -> None:
        async def scenario() -> tuple[bool, str, bool]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "#62" in _detail_text(app))
                await _open_spec(pilot)
                await _open_slices(pilot)

                return (
                    app.query_one(PullRequestPanel).display,
                    _detail_text(app),
                    app.query_one(SliceList).has_focus,
                )

        with _one_alive_loop_with([_reviewed_story()]):
            shown, text, list_focused = asyncio.run(scenario())

        assert shown is True
        assert "Slice 2 · PR #62" in text
        assert list_focused is True

    def test_should_not_expand_the_hidden_detail_with_the_spec_tab(self) -> None:
        async def scenario() -> Widget | None:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await _open_spec(pilot)
                await pilot.press("enter")
                await pilot.pause()

                return app.screen.maximized

        with _one_alive_loop_with([_reviewed_story()]):
            maximized = asyncio.run(scenario())

        assert maximized is None


def _styled_segments(static: Static) -> list[Segment]:
    console = Console(file=StringIO(), width=160, color_system="truecolor")
    content: Any = static.content

    return list(console.render(content))


def _rendered_rows(widget: Widget) -> list[list[Segment]]:
    return [list(strip) for strip in widget.render_lines(Region(0, 0, widget.size.width, widget.size.height))]


def _rail_lines(app: LoopsApp) -> list[str]:
    return ["".join(segment.text for segment in row) for row in _rendered_rows(_loop_list(app))]


def _first_cell(row: list[Segment]) -> tuple[str, Any]:
    first = row[0]

    return first.text[0], first.style.color if first.style is not None else None


def _content_background(row: list[Segment]) -> Any:
    return next(segment.style.bgcolor for segment in row if segment.text.strip(" ▌") and segment.style is not None)


def _rail_and_center_rows_after(presses: list[str]) -> tuple[list[Segment], list[Segment]]:
    async def scenario() -> tuple[list[Segment], list[Segment]]:
        app = _app()
        async with app.run_test(size=(160, 40)) as pilot:
            app.set_focus(_loop_list(app))
            await pilot.press(*presses)
            await pilot.pause()

            return _rendered_rows(_loop_list(app))[0], _rendered_rows(_row(app, "350"))[0]

    return asyncio.run(scenario())


class TestLoopsAppFrames:
    @pytest.mark.parametrize("zone", ["#loops", "#center", "#detail"])
    def test_should_frame_each_zone_with_a_rounded_border_over_the_panel_background(self, zone: str) -> None:
        async def scenario() -> tuple[list[str], Color, Color, int]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                styles = app.query_one(zone).styles

                return (
                    [
                        edge
                        for edge, _ in (
                            styles.border_top,
                            styles.border_right,
                            styles.border_bottom,
                            styles.border_left,
                        )
                    ],
                    styles.background,
                    Color.parse(app.get_css_variables()["panel"]),
                    styles.padding.left,
                )

        with _one_alive_loop_with([_reviewed_story()]):
            edges, background, panel, padding = asyncio.run(scenario())

        assert edges == ["round"] * 4
        assert background == panel
        assert padding == 1

    def test_should_leave_the_background_of_the_app_between_two_zones(self) -> None:
        async def scenario() -> list[int]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                zones = [app.query_one(zone).region for zone in ("#loops", "#center", "#detail")]

                return [right.x - left.right for left, right in pairwise(zones)]

        with _one_alive_loop_with([_reviewed_story()]):
            assert asyncio.run(scenario()) == [1, 1]

    def test_should_frame_the_detail_of_a_run_with_a_rounded_border(self) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()
                styles = app.query_one(RunPanel).styles

                return [
                    edge
                    for edge, _ in (styles.border_top, styles.border_right, styles.border_bottom, styles.border_left)
                ]

        with _one_alive_loop_with([_reviewed_story()]):
            assert asyncio.run(scenario()) == ["round"] * 4

    def test_should_leave_a_blank_line_between_two_slices(self, one_alive_loop_with_two_stories: Any) -> None:
        async def scenario() -> int:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _row(app, "351").region.y - _row(app, "350").region.bottom

        assert asyncio.run(scenario()) == 1

    def test_should_show_the_status_of_each_slice_as_a_chip_with_rounded_ends(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        async def scenario() -> tuple[str, list[Segment]]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _plain_text(_row(app, "351")), _styled_segments(_row(app, "351"))

        text, segments = asyncio.run(scenario())

        assert "◐ pr_open" in text
        assert any(
            "pr_open" in segment.text and segment.style.bgcolor is not None for segment in segments if segment.style
        )

    def test_should_tint_the_focused_row_and_draw_a_bar_on_its_left(self, one_alive_loop_with_two_stories: Any) -> None:
        async def scenario() -> tuple[str, str, bool]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab")
                focused, other = _row(app, "350").styles, _row(app, "351").styles

                return focused.border_left[0], other.border_left[0], focused.background != other.background

        focused_bar, other_bar, tinted = asyncio.run(scenario())

        assert focused_bar not in ("", "none", "blank")
        assert other_bar in ("", "none", "blank")
        assert tinted is True

    def test_should_leave_a_blank_line_between_two_loops_of_the_rail(
        self, two_alive_loops_with_a_tall_panel_and_a_silent_agent: Any
    ) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _rail_lines(app)

        lines = asyncio.run(scenario())
        second = next(index for index, line in enumerate(lines) if "verify/beta" in line)

        assert lines[second - 1].strip() == ""

    def test_should_leave_a_blank_line_between_the_alive_loops_and_the_idle_repos(
        self, one_alive_and_one_idle_loop: Any
    ) -> None:
        async def scenario() -> list[str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.pause()

                return _rail_lines(app)

        lines = asyncio.run(scenario())
        heading = next(index for index, line in enumerate(lines) if "NO LOOP" in line)

        assert lines[heading - 1].strip() == ""

    def test_should_highlight_the_loop_of_the_rail_like_the_focused_row_of_the_center(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        rail, _ = _rail_and_center_rows_after([])
        _, center = _rail_and_center_rows_after(["tab"])

        assert _first_cell(rail) == _first_cell(center)
        assert _content_background(rail) == _content_background(center)

    def test_should_dim_the_highlight_of_the_rail_like_the_center_when_neither_has_the_focus(
        self, one_alive_loop_with_two_stories: Any
    ) -> None:
        rail, center = _rail_and_center_rows_after(["tab", "tab"])

        assert _first_cell(rail) == _first_cell(center)
        assert _content_background(rail) == _content_background(center)


def _learned_story(conventions_pull_request_number: int | None = 70, resolved: bool = False) -> SnapshotStory:
    return SnapshotStory(
        number="338",
        status=SnapshotStoryStatus.SLICED,
        title="Learned story",
        slices=[
            SnapshotSlice(number="350", status=SnapshotSliceStatus.MERGED, title="Roles", pr_number="60"),
            SnapshotSlice(number="351", status=SnapshotSliceStatus.PR_OPEN, title="Permissions", pr_number="61"),
        ],
        lessons=[
            SnapshotLesson(
                number="286",
                source_pull_request_number=60,
                status=SnapshotLessonStatus.LEARNED if resolved else SnapshotLessonStatus.IN_PROGRESS,
                conventions_pull_request_number=conventions_pull_request_number,
                resolved=resolved,
            )
        ],
    )


def _conventions_detail() -> PullRequestDetail:
    return _commented_detail(70, conversation=[_REVIEW_SUMMARY], review=[])


def _highlighted_rows(app: LoopsApp) -> list[str | None]:
    return [row.id for row in app.query(ListRow) if row.has_class("-highlighted")]


def _comments_label(app: LoopsApp) -> str:
    tabs = app.query_one(PullRequestPanel).query_one(TabbedContent)

    return tabs.get_tab("pull-request-comments").label_text


class TestLoopsAppLessonLine:
    def test_should_reach_the_learning_line_of_a_slice_with_the_cursor_keys(self) -> None:
        async def scenario() -> tuple[list[str | None], list[str | None]]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                on_the_lesson = _highlighted_rows(app)
                await pilot.press("down")

                return on_the_lesson, _highlighted_rows(app)

        with _one_alive_loop_with([_learned_story()]):
            on_the_lesson, after_it = asyncio.run(scenario())

        assert on_the_lesson == ["lesson-350"]
        assert after_it == ["slice-351"]

    def test_should_highlight_the_learning_line_the_user_clicks(self) -> None:
        async def scenario() -> list[str | None]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.click("#lesson-350", offset=(2, 0))
                await pilot.pause()

                return _highlighted_rows(app)

        with _one_alive_loop_with([_learned_story()]):
            highlighted = asyncio.run(scenario())

        assert highlighted == ["lesson-350"]

    def test_should_show_the_conventions_pull_request_of_the_focused_learning_line_with_its_tabs(self) -> None:
        async def scenario() -> tuple[str, str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "PR #70" in _detail_text(app))

                return _detail_text(app), app.query_one(PullRequestBody).source, _comments_label(app)

        details = FakePullRequestDetails([_conventions_detail()])
        with _one_alive_loop_with([_learned_story()]), container.override(PullRequestDetails, details):
            text, body, comments = asyncio.run(scenario())

        assert "Lesson #286 · PR #70" in text
        assert "synced 40s ago" in text
        assert body == _BODY
        assert comments == "Comments 1"

    def test_should_show_only_the_summary_of_a_merged_conventions_pull_request(self) -> None:
        async def scenario() -> tuple[str, str, str]:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "PR #70" in _detail_text(app))

                return _detail_text(app), app.query_one(PullRequestBody).source, _comments_label(app)

        details = FakePullRequestDetails([_conventions_detail()])
        with _one_alive_loop_with([_learned_story(resolved=True)]), container.override(PullRequestDetails, details):
            text, body, comments = asyncio.run(scenario())

        assert "#70" in text
        assert "learned" in text
        assert "waiting" not in text
        assert body == ""
        assert comments == "Comments"

    def test_should_show_the_status_of_a_lesson_without_conventions_pull_request(self) -> None:
        async def scenario() -> str:
            app = _app()
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down")
                await _wait_for(pilot, lambda: "Lesson" in _detail_text(app))

                return _detail_text(app)

        with _one_alive_loop_with([_learned_story(conventions_pull_request_number=None)]):
            text = asyncio.run(scenario())

        assert "Lesson #286" in text
        assert "captured" in text
        assert "no conventions PR yet" in text

    def test_should_open_the_conventions_pull_request_of_the_focused_learning_line_with_o(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[str] = []

        async def scenario() -> None:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                await pilot.press("tab", "down", "o")

        with _one_alive_loop_with([_learned_story()]):
            asyncio.run(scenario())

        assert opened == ["https://github.com/verify/alfa/pull/70"]

    def test_should_focus_the_learning_line_whose_conventions_pull_request_number_the_user_clicks_without_opening_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[str] = []

        async def scenario() -> list[str | None]:
            app = _app()
            monkeypatch.setattr(app, "open_url", lambda url, **_: opened.append(url))
            async with app.run_test(size=(160, 40)) as pilot:
                line = app.query_one("#lesson-350", ListRow)
                await pilot.click(line, offset=_link_offset(line, "/pull/70"))
                await pilot.pause()

                return _highlighted_rows(app)

        with _one_alive_loop_with([_learned_story()]):
            highlighted = asyncio.run(scenario())

        assert opened == []
        assert highlighted == ["lesson-350"]

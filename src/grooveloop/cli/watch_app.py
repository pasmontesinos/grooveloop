from __future__ import annotations

import sys
from typing import TYPE_CHECKING, ClassVar

from rich.segment import Segment
from rich.style import Style as RichStyle
from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.strip import Strip
from textual.widgets import Footer, OptionList, Select, Static, TabbedContent, TabPane, Tabs
from textual.widgets.option_list import Option
from textual.worker import Worker, WorkerState

from grooveloop.cli.focus_path import FocusPath
from grooveloop.cli.loops_render import COLUMN_WIDTH, alive_prompt, idle_heading, idle_prompt, title
from grooveloop.cli.pull_request_panel import PullRequestPanel
from grooveloop.cli.repo_panel import story_lines
from grooveloop.cli.run_panel import RunPanel
from grooveloop.cli.slice_list import SliceList
from grooveloop.cli.story_journal import JournalEntries, StoryJournal
from grooveloop.cli.story_selector import StorySelector
from grooveloop.cli.story_spec import StorySpec
from grooveloop.cli.watch_render import RepoLinks, listed_stories
from grooveloop.shared.application.queries.list_loops import ListLoopsQuery
from grooveloop.shared.application.queries.read_journal_entries import ReadJournalEntriesQuery

if TYPE_CHECKING:
    from collections.abc import Sequence

    from textual.app import ComposeResult
    from textual.binding import BindingType
    from textual.pilot import Pilot
    from textual.widget import Widget

    from grooveloop.cli.watch_render import LearningLine, SessionLine, SliceLine, StoryLine
    from grooveloop.shared.application.queries.list_loops import ListLoopsQueryHandler, LoopDTO
    from grooveloop.shared.application.queries.query_bus import QueryBus
    from grooveloop.shared.application.queries.read_journal_entries import (
        JournalEntryDTO,
    )
    from grooveloop.shared.domain.agent_run_logs import AgentRunLogs
    from grooveloop.shared.domain.clock import Clock
    from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
    from grooveloop.shared.domain.pull_request_detail_reading import PullRequestDetailReading
    from grooveloop.shared.domain.pull_request_details import PullRequestDetails
    from grooveloop.shared.domain.story_spec_reading import StorySpecReading
    from grooveloop.shared.domain.story_specs import StorySpecs

_IDLE_HEADING_ID = "idle-heading"
_SCREENSHOT_SIZE = (160, 48)
_SLICES_TAB = "Slices"
_SLICES_PANE_ID = "slices"
_SPEC_TAB = "Spec"
_SPEC_PANE_ID = "spec"
_JOURNAL_TAB = "Journal"
_JOURNAL_PANE_ID = "journal"
_CLOSED_STATUSES = {"merged", "failed"}
CENTER_MIN_WIDTH = 52
_BAR = "loop-list--bar"
_BAR_CHARACTER = "▌"


def has_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


class LoopList(OptionList):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("enter", "select", "open")]
    COMPONENT_CLASSES: ClassVar[set[str]] = {_BAR}
    DEFAULT_CSS = f"""
    LoopList {{ height: auto; max-height: 1fr; border: none; background: $panel; padding: 0; }}
    LoopList:focus {{ border: none; background-tint: $foreground 0%; }}
    LoopList > .option-list--option {{ padding: 0 0 0 1; }}
    LoopList > .option-list--option-highlighted {{ color: $foreground; background: $accent 10%; text-style: none; }}
    LoopList:focus > .option-list--option-highlighted {{
        color: $foreground; background: $accent 25%; text-style: none;
    }}
    LoopList > .{_BAR} {{ color: $accent 50%; }}
    LoopList:focus > .{_BAR} {{ color: $accent; }}
    """

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)
        index = _option_index(strip)
        if index is None:
            return Strip.blank(strip.cell_length, self.get_visual_style("option-list--option").rich_style)

        if index != self.highlighted:
            return strip

        color = self.get_visual_style(_BAR).rich_style.color
        background = self.get_visual_style("option-list--option", "option-list--option-highlighted").rich_style
        bar = Segment(_BAR_CHARACTER, RichStyle(color=color, bgcolor=background.bgcolor))

        return Strip.join([Strip([bar], 1), strip.crop(1)])


class LoopsRail(Vertical):
    DEFAULT_CSS = f"""
    LoopsRail {{ width: {COLUMN_WIDTH}; border: round $border; background: $panel; padding: 0 1; margin: 0 1; }}
    LoopsRail > #loops-title {{ padding: 1 0; }}
    """


class StoryCenter(Vertical):
    DEFAULT_CSS = f"""
    StoryCenter {{
        width: 1fr; min-width: {CENTER_MIN_WIDTH};
        border: round $border; background: $panel; padding: 0 1; margin: 0 1 0 0;
    }}
    """


class LoopsApp(App[int]):
    ESCAPE_TO_MINIMIZE: ClassVar[bool] = False
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit_watch", "quit"),
        Binding("tab", "focus_next", "switch focus", priority=True),
        Binding("left_square_bracket", "previous_story", "previous Story", key_display="["),
        Binding("right_square_bracket", "next_story", "next Story", key_display="]"),
        Binding("enter", "expand_detail", "expand"),
        Binding("escape", "restore_columns", "back", key_display="esc"),
        Binding("o", "open_pull_request", "open on GitHub"),
    ]

    def __init__(
        self,
        handler: ListLoopsQueryHandler,
        snapshots: LoopSnapshots,
        details: PullRequestDetails,
        logs: AgentRunLogs,
        specs: StorySpecs,
        query_bus: QueryBus,
        clock: Clock,
        *,
        interval: float,
        stall_after: int,
    ) -> None:
        super().__init__()
        self._handler = handler
        self._snapshots = snapshots
        self._details = details
        self._logs = logs
        self._specs = specs
        self._query_bus = query_bus
        self._clock = clock
        self._interval = interval
        self._stall_after = stall_after
        self._selected: str | None = None
        self._loops: list[LoopDTO] = []
        self._repo: str | None = None
        self._stories: list[StoryLine] = []
        self._story: str | None = None
        self._focused_before_expanding: Widget | None = None
        self._reading: Worker[list[LoopDTO]] | None = None

    def compose(self) -> ComposeResult:
        yield FocusPath()
        with Horizontal():
            with LoopsRail(id="loops"):
                yield Static(id="loops-title")
                yield LoopList(id="loop-list")
            with StoryCenter(id="center"):
                yield StorySelector(id="story-selector")
                with TabbedContent(id="story-tabs"):
                    with TabPane(_SLICES_TAB, id=_SLICES_PANE_ID):
                        yield SliceList(stall_after=self._stall_after, id="panel")
                    with TabPane(_SPEC_TAB, id=_SPEC_PANE_ID):
                        yield StorySpec()
                    with TabPane(_JOURNAL_TAB, id=_JOURNAL_PANE_ID):
                        yield StoryJournal()
            yield PullRequestPanel(id="detail")
            yield RunPanel(self._logs, id="run-detail")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#story-tabs", TabbedContent).query_one(Tabs).can_focus = False
        await self._apply_loops(self._read_loops())
        self.set_interval(self._interval, self._refresh_loops)

    def capture(self, path: str) -> int:
        async def save_and_exit(pilot: Pilot[object]) -> None:
            await pilot.pause()
            self.save_screenshot(path)
            self.exit(0)

        return self.run(headless=True, size=_SCREENSHOT_SIZE, auto_pilot=save_and_exit) or 0

    def action_quit_watch(self) -> None:
        self.exit(0)

    def action_previous_story(self) -> None:
        self.query_one(StorySelector).choose_neighbour(-1)

    def action_next_story(self) -> None:
        self.query_one(StorySelector).choose_neighbour(1)

    def action_expand_detail(self) -> None:
        detail: Widget = self.query_one(PullRequestPanel)
        if not detail.display:
            detail = self.query_one(RunPanel)
        if not detail.display:
            return

        self._focused_before_expanding = self.focused
        self.screen.maximize(detail, container=False)

    def action_restore_columns(self) -> None:
        self.screen.minimize()
        if self._focused_before_expanding is not None:
            self._focused_before_expanding.focus()
            self._focused_before_expanding = None

    def action_open_pull_request(self) -> None:
        number = self._focused_pull_request_number()
        if self._repo is None or number is None:
            return

        self.open_url(RepoLinks(self._repo).pull(number))

    def _focused_pull_request_number(self) -> str | None:
        lesson = self.query_one(SliceList).highlighted_lesson
        if lesson is not None:
            return lesson.conventions_pr_number

        a_slice = self._focused_slice()

        return a_slice.pr_number if a_slice is not None else None

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._selected = event.option.id
        await self._show_loops()

    @on(Select.Changed, "#story-selector")
    def _choose_story(self) -> None:
        chosen = self.query_one(StorySelector).chosen_story
        if chosen is None or chosen == self._story:
            return

        self._story = chosen
        self._show_story()
        self.query_one(SliceList).scroll_home(animate=False)
        self.query_one(StoryJournal).show_latest()

    @on(TabbedContent.TabActivated, "#story-tabs", pane="#slices")
    def _open_slices(self) -> None:
        self._show_focus()
        tabs = self.query_one("#story-tabs", TabbedContent)
        if self.focused is not None and tabs in self.focused.ancestors:
            self.query_one(SliceList).focus()

    @on(TabbedContent.TabActivated, "#story-tabs", pane="#spec")
    def _open_spec(self) -> None:
        self._show_focus()
        self.query_one(StorySpec).focus()

    @on(TabbedContent.TabActivated, "#story-tabs", pane="#journal")
    def _open_journal(self) -> None:
        self._show_focus()
        self.query_one(StoryJournal).show_latest()
        self.query_one(JournalEntries).focus()

    def on_slice_list_highlight_changed(self) -> None:
        self._show_focus()

    def _refresh_loops(self) -> None:
        if not self.is_running or (self._reading is not None and not self._reading.is_finished):
            return

        self._reading = self.run_worker(self._read_loops, thread=True)

    def _read_loops(self) -> list[LoopDTO]:
        return self._handler(ListLoopsQuery(stall_after_seconds=self._stall_after)).loops

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        reading = self._reading
        if event.worker is not reading or event.state != WorkerState.SUCCESS or reading.result is None:
            return

        if self.is_running:
            await self._apply_loops(reading.result)

    async def _apply_loops(self, loops: list[LoopDTO]) -> None:
        self._loops = loops
        alive = [loop.repo for loop in self._loops if loop.alive]
        if self._selected not in alive:
            self._selected = alive[0] if len(alive) > 0 else None

        await self._show_loops()

    async def _show_loops(self) -> None:
        alive = [loop for loop in self._loops if loop.alive]
        self.query_one("#loops-title", Static).update(title(len(alive)))
        self._show_options()
        await self._show_panel(alive)

    def _show_options(self) -> None:
        loop_list = self.query_one("#loop-list", LoopList)
        options = self._options()
        if _layout(loop_list.options) == _layout(options):
            for option in options:
                if option.id is not None:
                    loop_list.replace_option_prompt(option.id, option.prompt)

            return

        highlighted = loop_list.highlighted_option
        highlighted_id = highlighted.id if highlighted is not None else self._selected
        loop_list.set_options(_with_gaps(options))
        enabled = [option.id for option in options if not option.disabled]
        if highlighted_id is not None and highlighted_id in enabled:
            loop_list.highlighted = loop_list.get_option_index(highlighted_id)
        elif len(enabled) > 0:
            loop_list.highlighted = 0

    def _options(self) -> list[Option]:
        options = [
            Option(alive_prompt(loop, selected=loop.repo == self._selected), id=loop.repo)
            for loop in self._loops
            if loop.alive
        ]
        idle = [loop for loop in self._loops if not loop.alive]
        if len(idle) > 0:
            options.append(Option(idle_heading(), id=_IDLE_HEADING_ID, disabled=True))
            options.extend(Option(idle_prompt(loop), id=loop.repo, disabled=True) for loop in idle)

        return options

    async def _show_panel(self, alive: list[LoopDTO]) -> None:
        self._choose_story()
        loop = next((loop for loop in alive if loop.repo == self._selected), None)
        self._repo = loop.repo if loop is not None else None
        self._stories = self._listed_stories(loop)
        numbers = [story.number for story in self._stories]
        if self._story not in numbers:
            self._story = next(iter(numbers), None)

        self.query_one(StorySelector).show_stories(self._stories, self._story)
        self._show_story()

    def _listed_stories(self, loop: LoopDTO | None) -> list[StoryLine]:
        if loop is None:
            return []

        snapshot = self._snapshots.find(loop.repo)
        if snapshot is None:
            return []

        return listed_stories(story_lines(snapshot.stories, loop.sessions, self._clock.now()))

    def _show_story(self) -> None:
        story = self._chosen_story()
        self.query_one(SliceList).show(self._repo, [story] if story is not None else [])
        self.query_one(StorySpec).show(self._spec_reading())
        self._show_journal()
        self._show_focus()

    def _spec_reading(self) -> StorySpecReading | None:
        if self._repo is None or self._story is None:
            return None

        return self._specs.read(self._repo, int(self._story))

    def _show_journal(self) -> None:
        entries = self._journal_entries()
        self.query_one("#story-tabs", TabbedContent).get_tab(_JOURNAL_PANE_ID).label = f"{_JOURNAL_TAB} {len(entries)}"
        self.query_one(StoryJournal).show(entries, self._clock.now())

    def _journal_entries(self) -> list[JournalEntryDTO]:
        if self._repo is None or self._story is None:
            return []

        return self._query_bus.ask(ReadJournalEntriesQuery(repo=self._repo, story_id=self._story)).entries

    def _show_focus(self) -> None:
        a_slice = self._focused_slice()
        session = self._focused_session(a_slice)
        self.query_one(FocusPath).show(self._repo, self._chosen_story(), a_slice)
        pull_request_panel = self.query_one(PullRequestPanel)
        run_panel = self.query_one(RunPanel)
        on_slices = self.query_one("#story-tabs", TabbedContent).active == _SLICES_PANE_ID
        pull_request_panel.display = on_slices and session is None
        run_panel.display = on_slices and session is not None
        lesson = self.query_one(SliceList).highlighted_lesson
        if a_slice is not None and session is not None:
            run_panel.show(a_slice, session)
        elif lesson is not None:
            pull_request_panel.show_lesson(lesson, self._lesson_reading(lesson), self._clock.now())
        else:
            pull_request_panel.show(a_slice, self._detail_reading(a_slice), self._clock.now())

    def _focused_session(self, a_slice: SliceLine | None) -> SessionLine | None:
        run_id = self.query_one(SliceList).highlighted_run
        if a_slice is None or run_id is None:
            return None

        return next((session for session in a_slice.sessions if session.run_id == run_id), None)

    def _detail_reading(self, a_slice: SliceLine | None) -> PullRequestDetailReading | None:
        if self._repo is None or a_slice is None or a_slice.pr_number is None or a_slice.status in _CLOSED_STATUSES:
            return None

        return self._details.read(self._repo, int(a_slice.pr_number))

    def _lesson_reading(self, lesson: LearningLine) -> PullRequestDetailReading | None:
        if self._repo is None or lesson.conventions_pr_number is None or lesson.resolved:
            return None

        return self._details.read(self._repo, int(lesson.conventions_pr_number))

    def _focused_slice(self) -> SliceLine | None:
        story = self._chosen_story()
        number = self.query_one(SliceList).highlighted_slice
        slices = story.slices if story is not None else []

        return next((a_slice for a_slice in slices if a_slice.number == number), None)

    def _chosen_story(self) -> StoryLine | None:
        return next((story for story in self._stories if story.number == self._story), None)


def _with_gaps(options: list[Option]) -> list[Option | None]:
    spaced: list[Option | None] = []
    for option, following in zip(options, [*options[1:], None], strict=True):
        spaced.append(option)
        if not option.disabled and following is not None:
            spaced.append(None)

    return spaced


def _option_index(strip: Strip) -> int | None:
    return next(
        (
            segment.style.meta["option"]
            for segment in strip
            if segment.style is not None and "option" in segment.style.meta
        ),
        None,
    )


def _layout(options: Sequence[Option]) -> list[tuple[str | None, bool]]:
    return [(option.id, option.disabled) for option in options]

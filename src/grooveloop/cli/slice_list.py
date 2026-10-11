from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar

from rich.console import Group
from rich.padding import Padding
from rich.table import Table
from rich.text import Text
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from grooveloop.cli.palette import FOCUS, MUTED, STATUS_STYLES, WARNING, tint
from grooveloop.cli.watch_render import (
    ACTION_MARK,
    STATUS_ICONS,
    RepoLinks,
    SessionTable,
    column_widths,
    issue_url,
    learning_line,
    link,
    session_row,
    story_header,
)

if TYPE_CHECKING:
    from rich.console import RenderableType
    from textual.binding import BindingType
    from textual.widget import Widget

    from grooveloop.cli.watch_render import LearningLine, SessionLine, SliceLine, StoryLine

_HIGHLIGHTED = "-highlighted"
_NEEDED = "-needed"
_UNBLOCKED = "-unblocked"
_MARKS = {_NEEDED: Text("▲", style=f"bold {WARNING}"), _UNBLOCKED: Text("▼", style=f"bold {FOCUS}")}
_DEPENDENCIES_MARK = "←"
_ROW_PREFIX = "slice-"
_RUN_PREFIX = "run-"
_COLUMN_GAP = 1
_ACTION_INDENT = 2
_CHIP_START = "\ue0b6"
_CHIP_END = "\ue0b4"


class StoryHeading(Static):
    pass


class StoryLessons(Static):
    pass


class ListRow(Static):
    class Picked(Message):
        def __init__(self, row: ListRow) -> None:
            super().__init__()
            self.row = row

    def on_click(self) -> None:
        self.post_message(self.Picked(self))


class SliceRow(ListRow):
    pass


class SessionRow(ListRow):
    pass


class LessonRow(ListRow):
    pass


class SliceList(VerticalScroll, can_focus=True):
    class HighlightChanged(Message):
        def __init__(self, slice_number: str | None) -> None:
            super().__init__()
            self.slice_number = slice_number

    DEFAULT_CSS = """
    SliceList { width: 1fr; scrollbar-gutter: stable; }
    SliceList > StoryHeading { padding: 0 1; margin-top: 1; }
    SliceList > StoryLessons { padding: 0 1 0 3; }
    SliceList > ListRow { padding: 0 1 0 0; border-left: blank; }
    SliceList > SliceRow { margin-top: 1; }
    SliceList > ListRow.-highlighted { background: $accent 10%; border-left: outer $accent 50%; }
    SliceList:focus > ListRow.-highlighted { background: $accent 25%; border-left: outer $accent; }
    SliceList > SliceRow.-needed { background: $warning 15%; }
    SliceList > SliceRow.-unblocked { background: $accent 15%; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", show=False),
        Binding("down", "cursor_down", show=False),
    ]

    def __init__(self, *, stall_after: int, id: str) -> None:
        super().__init__(id=id)
        self._stall_after = stall_after
        self._lines: dict[str, Static] = {}
        self._rows: dict[str, _Row] = {}
        self._painted: dict[str, _Paint] = {}
        self._highlighted: str | None = None

    @property
    def highlighted_slice(self) -> str | None:
        row = self._highlighted_row()

        return row.a_slice.number if row is not None else None

    @property
    def highlighted_run(self) -> str | None:
        row = self._highlighted_row()
        if row is None or row.session is None:
            return None

        return row.session.run_id

    @property
    def highlighted_lesson(self) -> LearningLine | None:
        row = self._highlighted_row()

        return row.learning if row is not None else None

    def show(self, repo: str | None, stories: list[StoryLine]) -> None:
        if repo is None:
            self._show_lines([])

            return

        self._show_lines(_lines(stories, RepoLinks(repo), self._stall_after))

    def action_cursor_up(self) -> None:
        self._move(-1)

    def action_cursor_down(self) -> None:
        self._move(1)

    def on_list_row_picked(self, message: ListRow.Picked) -> None:
        self._highlight(message.row.id)
        self.focus()

    def _move(self, step: int) -> None:
        rows = list(self._rows)
        if len(rows) == 0:
            return

        index = rows.index(self._highlighted) if self._highlighted in rows else 0
        target = rows[max(0, min(len(rows) - 1, index + step))]
        self._highlight(target)
        self._lines[target].scroll_visible(animate=False)

    def _show_lines(self, lines: list[_Line]) -> None:
        self._rows = {line.id: line.row for line in lines if line.row is not None}
        wanted = {line.id for line in lines}
        for line_id in [line_id for line_id in self._lines if line_id not in wanted]:
            self._lines.pop(line_id).remove()
            self._painted.pop(line_id, None)

        anchor: Widget | None = None
        for line in lines:
            widget = self._lines.get(line.id)
            if widget is None:
                widget = line.kind(line.content, id=line.id)
                self._lines[line.id] = widget
                self._mount_after(widget, anchor)
            else:
                if line.row is None:
                    widget.update(line.content)
                self._move_after(widget, anchor)

            anchor = widget

        self._highlight(self._highlighted if self._highlighted in self._rows else next(iter(self._rows), None))

    def _mount_after(self, widget: Widget, anchor: Widget | None) -> None:
        if anchor is not None:
            self.mount(widget, after=anchor)
        elif len(self.children) > 0:
            self.mount(widget, before=0)
        else:
            self.mount(widget)

    def _move_after(self, widget: Widget, anchor: Widget | None) -> None:
        position = 0 if anchor is None else self.children.index(anchor) + 1
        if self.children.index(widget) == position:
            return

        if anchor is None:
            self.move_child(widget, before=0)
        else:
            self.move_child(widget, after=anchor)

    def _highlighted_row(self) -> _Row | None:
        if self._highlighted is None:
            return None

        return self._rows.get(self._highlighted)

    def _highlight(self, row_id: str | None) -> None:
        changed = row_id != self._highlighted
        self._highlighted = row_id
        self._paint_rows()
        if changed:
            self.post_message(self.HighlightChanged(self.highlighted_slice))

    def _paint_rows(self) -> None:
        focused = self._highlighted_row()
        for row_id, row in self._rows.items():
            paint = _Paint(_drawn(row), row_id == self._highlighted, _row_relation(row, focused))
            if self._painted.get(row_id) == paint:
                continue

            self._painted[row_id] = paint
            _paint(self._lines[row_id], row, paint)


@dataclass(frozen=True)
class _Row:
    a_slice: SliceLine
    dependencies: Text
    layout: _Layout
    session: SessionLine | None = None
    learning: LearningLine | None = None


@dataclass(frozen=True)
class _Paint:
    drawn: object
    highlighted: bool
    relation: str | None


@dataclass(frozen=True)
class _Line:
    id: str
    kind: type[Static]
    content: RenderableType
    row: _Row | None = None


@dataclass(frozen=True)
class _Layout:
    links: RepoLinks
    stall_after_seconds: int
    order_width: int
    dependencies_width: int
    status_width: int
    pr_width: int
    session_widths: list[int]


def _lines(stories: list[StoryLine], links: RepoLinks, stall_after_seconds: int) -> list[_Line]:
    layout = _layout(stories, links, stall_after_seconds)
    lines: list[_Line] = []
    for story in stories:
        lines.append(_Line(f"story-{story.number}", StoryHeading, story_header(story, links)))
        orders = _orders(story)
        for a_slice in story.slices:
            lines.extend(_slice_lines(a_slice, _Row(a_slice, _dependencies(a_slice, orders), layout)))
        if len(story.lessons) > 0:
            lessons = Group(*[learning_line(lesson, links) for lesson in story.lessons])
            lines.append(_Line(f"lessons-{story.number}", StoryLessons, lessons))

    return lines


def _slice_lines(a_slice: SliceLine, row: _Row) -> list[_Line]:
    lines = [_Line(f"{_ROW_PREFIX}{a_slice.number}", SliceRow, Text(), row)]
    lines.extend(
        _Line(f"{_RUN_PREFIX}{session.run_id}", SessionRow, Text(), replace(row, session=session))
        for session in a_slice.sessions
    )
    if a_slice.learning is not None:
        lines.append(_Line(f"lesson-{a_slice.number}", LessonRow, Text(), replace(row, learning=a_slice.learning)))

    return lines


def _layout(stories: list[StoryLine], links: RepoLinks, stall_after_seconds: int) -> _Layout:
    slices = [a_slice for story in stories for a_slice in story.slices]
    rows = [session_row(session, stall_after_seconds) for a_slice in slices for session in a_slice.sessions]

    return _Layout(
        links=links,
        stall_after_seconds=stall_after_seconds,
        order_width=max((len(str(a_slice.order)) for a_slice in slices), default=0),
        dependencies_width=max(
            (_dependencies(a_slice, _orders(story)).cell_len for story in stories for a_slice in story.slices),
            default=0,
        ),
        status_width=max((_status(a_slice).cell_len for a_slice in slices), default=0),
        pr_width=max((_pull_request(a_slice, links).cell_len for a_slice in slices), default=0),
        session_widths=column_widths(rows),
    )


def _paint(widget: Static, row: _Row, paint: _Paint) -> None:
    widget.set_class(paint.highlighted, _HIGHLIGHTED)
    if row.learning is not None:
        widget.update(_lesson_row(row, row.learning))

        return

    if row.session is not None:
        widget.update(_session_row(row, row.session))

        return

    widget.set_class(paint.relation == _NEEDED, _NEEDED)
    widget.set_class(paint.relation == _UNBLOCKED, _UNBLOCKED)
    widget.update(_slice_row(row, _MARKS[paint.relation] if paint.relation is not None else Text()))


def _drawn(row: _Row) -> object:
    layout = row.layout
    if row.learning is not None:
        return row.learning, layout.links, layout.order_width

    if row.session is not None:
        return row.session, layout.order_width, layout.stall_after_seconds, layout.session_widths

    a_slice = row.a_slice

    return (
        a_slice.order,
        a_slice.title,
        a_slice.number,
        a_slice.status,
        a_slice.pr_number,
        row.dependencies.plain,
        layout.links,
        layout.order_width,
        layout.dependencies_width,
        layout.status_width,
        layout.pr_width,
    )


def _slice_row(row: _Row, mark: Text) -> Table:
    a_slice = row.a_slice
    layout = row.layout
    cells: list[RenderableType] = [
        Text(str(a_slice.order)),
        link(a_slice.title, issue_url(layout.links, a_slice.number)),
    ]
    line = Table.grid(expand=True, padding=(0, _COLUMN_GAP, 0, 0))
    line.add_column(justify="right", width=layout.order_width)
    line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    if layout.dependencies_width > 0:
        line.add_column(width=layout.dependencies_width, no_wrap=True)
        cells.append(row.dependencies)

    line.add_column(width=layout.status_width, no_wrap=True)
    line.add_column(width=1, no_wrap=True)
    line.add_column(justify="right", width=layout.pr_width, no_wrap=True)
    line.add_row(*cells, _status(a_slice), mark, _pull_request(a_slice, layout.links))

    return line


def _session_row(row: _Row, session: SessionLine) -> Group:
    layout = row.layout
    indent = _indent(layout)
    session_cells = session_row(session, layout.stall_after_seconds)
    parts: list[RenderableType] = [Padding(SessionTable([session_cells], layout.session_widths), (0, 0, 0, indent))]
    if session.last_action is not None:
        action = Text(f"{ACTION_MARK} {session.last_action}", style=MUTED)
        parts.append(Padding(action, (0, 0, 0, indent + _ACTION_INDENT)))

    return Group(*parts)


def _lesson_row(row: _Row, learning: LearningLine) -> Padding:
    return Padding(learning_line(learning, row.layout.links), (0, 0, 0, _indent(row.layout)))


def _indent(layout: _Layout) -> int:
    return layout.order_width + _COLUMN_GAP


def _orders(story: StoryLine) -> dict[str, int]:
    return {a_slice.number: a_slice.order for a_slice in story.slices}


def _dependencies(a_slice: SliceLine, orders: dict[str, int]) -> Text:
    if len(a_slice.depends_on) == 0:
        return Text()

    shown = [str(orders[number]) if number in orders else f"#{number}" for number in a_slice.depends_on]

    return Text(f"{_DEPENDENCIES_MARK} {', '.join(shown)}", style=MUTED)


def _row_relation(row: _Row, focused: _Row | None) -> str | None:
    if focused is None or row.session is not None or row.learning is not None:
        return None

    return _relation(row.a_slice, focused.a_slice)


def _relation(a_slice: SliceLine, focused: SliceLine) -> str | None:
    if a_slice.number in focused.depends_on:
        return _NEEDED

    if focused.number in a_slice.depends_on:
        return _UNBLOCKED

    return None


def _status(a_slice: SliceLine) -> Text:
    color = STATUS_STYLES.get(a_slice.status, MUTED)
    background = tint(color)

    return Text.assemble(
        (_CHIP_START, background),
        (f"{STATUS_ICONS[a_slice.status]} {a_slice.status}", f"{color} on {background}"),
        (_CHIP_END, background),
    )


def _pull_request(a_slice: SliceLine, links: RepoLinks) -> Text:
    if a_slice.pr_number is None:
        return Text()

    return link(f"#{a_slice.pr_number}", links.pull(a_slice.pr_number))

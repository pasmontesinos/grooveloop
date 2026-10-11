from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from grooveloop.cli.elapsed import format_elapsed
from grooveloop.cli.palette import MUTED, OUTCOME_STYLES, STATUS_STYLES, WARNING

if TYPE_CHECKING:
    from rich.console import ConsoleOptions, JustifyMethod, RenderResult


_WIP = "WIP"
_SLICED = "Sliced"
_READY = "Ready"
_DONE = "Done"
_PHASES = (_WIP, _SLICED, _READY, _DONE)
_DRAFT_STATUS = "draft"
_READY_STATUS = "ready_for_implementation"
_DONE_STATUS = "done"
_MERGED_STATUS = "merged"
_PENDING_STATUS = "pending"

STATUS_ICONS = {
    "pending": "○",
    "dispatched": "◔",
    "under_review": "◓",
    "pr_open": "◐",
    "changes_requested": "◑",
    "blocked": "⏸",
    "merged": "●",
    "failed": "✗",
}
_STATUS_ORDER = tuple(STATUS_ICONS)
OUTCOME_ICONS = {"running": "▶", "done": "✓", "interrupted": "↯", "failed": "✗", "unstarted": "·"}
_RUNNING_OUTCOME = "running"
_UNSTARTED_OUTCOME = "unstarted"
LESSON_LABELS = {
    "in_progress": "captured",
    "learned": "learned",
    "discarded": "discarded",
}
_PENDING_LESSON_MARK = "✎"
_RESOLVED_LESSON_MARK = "✓"
_STALL_STYLE = f"bold {WARNING}"
_ELAPSED_MARK = "⏱"
_COLUMN_GAP = 1
_LEFT: JustifyMethod = "left"
_RIGHT: JustifyMethod = "right"
_SESSION_JUSTIFY = [_LEFT] * 5 + [_RIGHT] * 5 + [_LEFT] + [_RIGHT] * 4 + [_LEFT]
_HIDING_ORDER = [[14], [8], [12, 13], [7, 9], [10, 11], [2], [3], [6]]
ACTION_MARK = "↳"
_TALLY_MARK = "Σ"
DEFAULT_STALL_AFTER_SECONDS = 300
DEFAULT_WIDTH = 200
_THOUSAND = 1_000
_MILLION = 1_000_000

_OSC8_PARAMS = re.compile(r"\x1b\]8;[^;]*;")
_SGR = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class RepoLinks:
    repo_full_name: str

    def issue(self, number: str) -> str:
        return f"https://github.com/{self.repo_full_name}/issues/{number}"

    def pull(self, number: str) -> str:
        return f"https://github.com/{self.repo_full_name}/pull/{number}"


@dataclass(frozen=True)
class ModelLine:
    model: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int


@dataclass(frozen=True)
class ToolTallyLine:
    name: str
    count: int


@dataclass(frozen=True)
class CostShareLine:
    token_class: str
    tokens: int
    cost_usd: float | None


@dataclass(frozen=True)
class SessionLine:
    outcome: str
    task_type: str
    engine: str
    elapsed_seconds: float
    run_id: str
    profile: str | None = None
    total_cost_usd: float | None = None
    models: list[ModelLine] = field(default_factory=list)
    launch_model: str | None = None
    silent_seconds: float | None = None
    last_action: str | None = None
    turns: int | None = None
    subagents: int | None = None
    skills: list[str] = field(default_factory=list)
    tools: list[ToolTallyLine] = field(default_factory=list)
    cost_shares: list[CostShareLine] = field(default_factory=list)
    cause: str | None = None


@dataclass(frozen=True)
class LearningLine:
    number: str | None = None
    status: str = "in_progress"
    conventions_pr_number: str | None = None
    resolved: bool = False


@dataclass(frozen=True)
class PullRequestLine:
    title: str
    additions: int
    deletions: int
    changed_files: int
    mergeable: str
    checks: str | None
    age_seconds: int


@dataclass(frozen=True)
class SliceLine:
    status: str
    title: str
    order: int
    pr_number: str | None = None
    number: str = ""
    sessions: list[SessionLine] = field(default_factory=list)
    learning: LearningLine | None = None
    blocked_by_order: int | None = None
    depends_on: list[str] = field(default_factory=list)
    pull_request: PullRequestLine | None = None


@dataclass(frozen=True)
class StoryLine:
    number: str
    title: str
    status: str
    slices: list[SliceLine]
    lessons: list[LearningLine] = field(default_factory=list)


@dataclass(frozen=True)
class SessionTable:
    rows: list[list[Text]]
    widths: list[int]

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        shown = fitting_columns(self.widths, options.max_width)
        aligned = _row_width(self.widths, shown) <= options.max_width
        table = Table.grid(padding=(0, _COLUMN_GAP, 0, 0))
        for column in shown:
            table.add_column(
                justify=_SESSION_JUSTIFY[column],
                min_width=self.widths[column] if aligned else None,
                overflow="fold",
            )

        for row in self.rows:
            table.add_row(*[row[column] for column in shown])

        yield table


@dataclass(frozen=True)
class StoryBlock:
    number: str
    header: Text
    body: Tree


def render(
    stories: list[StoryLine],
    links: RepoLinks | None = None,
    color: bool | None = None,
    stall_after_seconds: int = DEFAULT_STALL_AFTER_SECONDS,
    width: int = DEFAULT_WIDTH,
) -> str:
    use_color = sys.stdout.isatty() if color is None else color

    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=True,
        color_system="truecolor",
        width=width,
        highlight=False,
        emoji=False,
    )

    for block in story_blocks(stories, links, stall_after_seconds):
        console.print(_story_tree(block))

    frame = _normalize_links(buffer.getvalue())

    return frame if use_color else _SGR.sub("", frame)


def story_blocks(
    stories: list[StoryLine],
    links: RepoLinks | None = None,
    stall_after_seconds: int = DEFAULT_STALL_AFTER_SECONDS,
) -> list[StoryBlock]:
    listed = listed_stories(stories)
    rows = [
        [[session_row(session, stall_after_seconds) for session in a_slice.sessions] for a_slice in story.slices]
        for story in listed
    ]
    widths = column_widths([row for story_rows in rows for slice_rows in story_rows for row in slice_rows])

    return [
        StoryBlock(
            number=story.number,
            header=story_header(story, links),
            body=_story_body(story, links, story_rows, widths),
        )
        for story, story_rows in zip(listed, rows, strict=True)
    ]


def listed_stories(stories: list[StoryLine]) -> list[StoryLine]:
    by_phase: dict[str, list[StoryLine]] = {phase: [] for phase in _PHASES}
    for story in stories:
        by_phase[_phase_of(story)].append(story)

    return _listed_by_phase(by_phase)


def _listed_by_phase(by_phase: dict[str, list[StoryLine]]) -> list[StoryLine]:
    if len(by_phase[_WIP]) > 0:
        return by_phase[_WIP]

    if len(by_phase[_SLICED]) > 0 or len(by_phase[_READY]) > 0:
        return []

    return _last_done(by_phase[_DONE])


def _last_done(stories: list[StoryLine]) -> list[StoryLine]:
    worked = [(story, seconds) for story in stories if (seconds := _seconds_since_last_session(story)) is not None]
    if len(worked) == 0:
        return []

    return [min(worked, key=lambda pair: pair[1])[0]]


def _seconds_since_last_session(story: StoryLine) -> float | None:
    ages = [
        session.silent_seconds
        for a_slice in story.slices
        for session in a_slice.sessions
        if session.silent_seconds is not None
    ]
    if len(ages) == 0:
        return None

    return min(ages)


def _story_tree(block: StoryBlock) -> Tree:
    tree = Tree(block.header)
    tree.children.extend(block.body.children)

    return tree


def _story_body(story: StoryLine, links: RepoLinks | None, rows: list[list[list[Text]]], widths: list[int]) -> Tree:
    tree = Tree("", hide_root=True)
    for a_slice, slice_rows in zip(story.slices, rows, strict=True):
        tree.add(_slice_label(a_slice, links, slice_rows, widths))

    for lesson in story.lessons:
        tree.add(learning_line(lesson, links))

    return tree


def story_header(story: StoryLine, links: RepoLinks | None) -> Text:
    header = _story_label(story, links)
    header.append(f"   {_status_summary(story)}")

    return header


def _status_summary(story: StoryLine) -> str:
    phase = _phase_of(story)
    counts = Counter(a_slice.status for a_slice in story.slices)
    parts = [f"{counts[status]} {status}" for status in _STATUS_ORDER if counts[status] > 0]
    lessons = _lessons_of(story)
    pending = sum(1 for lesson in lessons if not lesson.resolved)
    if pending > 0:
        parts.append(f"{pending} learning")

    resolved = sum(1 for lesson in lessons if lesson.resolved)
    if resolved > 0:
        parts.append(f"{resolved} learning ✓")

    if len(parts) == 0:
        return phase

    return f"{phase} · " + " · ".join(parts)


def _slice_label(a_slice: SliceLine, links: RepoLinks | None, rows: list[list[Text]], widths: list[int]) -> Group:
    label = Text()
    label.append(f"{STATUS_ICONS[a_slice.status]} {a_slice.status}", style=STATUS_STYLES.get(a_slice.status, ""))
    label.append(f"   {a_slice.order} · ")
    label.append_text(link(a_slice.title, issue_url(links, a_slice.number)))
    if a_slice.blocked_by_order is not None:
        label.append(f"   ⏸ blocked by the learning of slice {a_slice.blocked_by_order}", style=MUTED)

    parts: list[Text | SessionTable] = [label]
    if len(rows) > 0:
        parts.append(SessionTable(rows, widths))

    parts.extend(
        Text(f"  {ACTION_MARK} {session.last_action}", style=MUTED)
        for session in a_slice.sessions
        if session.last_action is not None
    )
    if a_slice.learning is not None:
        parts.append(learning_line(a_slice.learning, links))

    return Group(*parts)


def learning_line(learning: LearningLine, links: RepoLinks | None) -> Text:
    mark = _RESOLVED_LESSON_MARK if learning.resolved else _PENDING_LESSON_MARK
    line = Text()
    line.append(f"{mark} lesson ", style=MUTED)
    if learning.number is not None:
        line.append_text(link(f"#{learning.number}", issue_url(links, learning.number)))

    line.append(f"   {LESSON_LABELS[learning.status]}", style=MUTED)
    if learning.conventions_pr_number is not None:
        line.append("   → PR ", style=MUTED)
        pull_url = links.pull(learning.conventions_pr_number) if links is not None else None
        line.append_text(link(f"#{learning.conventions_pr_number}", pull_url))

    return line


def fitting_columns(widths: list[int], max_width: int) -> list[int]:
    shown = [column for column, width in enumerate(widths) if width > 0]
    for hidden in _HIDING_ORDER:
        if _row_width(widths, shown) <= max_width:
            break

        shown = [column for column in shown if column not in hidden]

    return shown


def _row_width(widths: list[int], shown: list[int]) -> int:
    return sum(widths[column] for column in shown) + _COLUMN_GAP * (len(shown) - 1)


def column_widths(rows: list[list[Text]]) -> list[int]:
    return [max((row[column].cell_len for row in rows), default=0) for column in range(len(_SESSION_JUSTIFY))]


def session_row(session: SessionLine, stall_after_seconds: int) -> list[Text]:
    return [
        Text(OUTCOME_ICONS[session.outcome], style=OUTCOME_STYLES[session.outcome]),
        *_dim_cells(
            session.task_type,
            session.engine,
            _format_model(session.launch_model),
            _ELAPSED_MARK,
            format_elapsed(session.elapsed_seconds),
            _format_cost(session.total_cost_usd),
            *_token_cells(session.models),
            *_tally_cells(session),
        ),
        _state_cell(session, stall_after_seconds),
    ]


def _dim_cells(*values: str) -> list[Text]:
    return [Text(value, style=MUTED) for value in values]


def _state_cell(session: SessionLine, stall_after_seconds: int) -> Text:
    cell = Text()
    if session.outcome == _RUNNING_OUTCOME:
        cell.append("LIVE", style=MUTED)

    if session.outcome == _UNSTARTED_OUTCOME:
        cell.append("not started", style=MUTED)

    if session.cause is not None:
        cell.append(session.cause, style=OUTCOME_STYLES[session.outcome])

    if _is_silent(session, stall_after_seconds):
        cell.append(f"   ⚠ stalled {format_elapsed(session.silent_seconds)}", style=_STALL_STYLE)

    return cell


def _is_silent(session: SessionLine, stall_after_seconds: int) -> bool:
    if session.outcome != _RUNNING_OUTCOME or session.silent_seconds is None:
        return False

    return session.silent_seconds >= stall_after_seconds


def _format_cost(cost: float | None) -> str:
    if cost is None:
        return "—"

    return f"${cost:.4f}"


def _format_model(model: str | None) -> str:
    if model is None:
        return "—"

    return model


def _token_cells(models: list[ModelLine]) -> list[str]:
    if len(models) == 0:
        return ["", "", ""]

    return [
        f"↑{format_tokens(_input_tokens(models))}",
        f"{_cached_share(models):.1f}% cached",
        f"↓{format_tokens(_output_tokens(models))}",
    ]


def _input_tokens(models: list[ModelLine]) -> int:
    return sum(model.input_tokens + model.cache_read_tokens + model.cache_creation_tokens for model in models)


def _output_tokens(models: list[ModelLine]) -> int:
    return sum(model.output_tokens for model in models)


def _cached_share(models: list[ModelLine]) -> float:
    total = _input_tokens(models)
    if total == 0:
        return 0.0

    return 100.0 * sum(model.cache_read_tokens for model in models) / total


def _tally_cells(session: SessionLine) -> list[str]:
    if session.turns is None:
        return ["", "", "", "", ""]

    return [
        _TALLY_MARK,
        f"{session.turns}t",
        f"{len(session.skills)}sk",
        f"{_format_subagents(session.subagents)}sub",
        f"{_total_tools(session)}tl",
    ]


def _total_tools(session: SessionLine) -> int:
    return sum(tool.count for tool in session.tools)


def _format_subagents(subagents: int | None) -> str:
    return "—" if subagents is None else str(subagents)


def format_tokens(tokens: int) -> str:
    if tokens < _THOUSAND:
        return str(tokens)

    if tokens < _MILLION:
        return f"{tokens / _THOUSAND:.1f}K"

    return f"{tokens / _MILLION:.1f}M"


def _story_label(story: StoryLine, links: RepoLinks | None) -> Text:
    label = link(f"#{story.number}", issue_url(links, story.number))
    label.append(f"  {story.title}")

    return label


def link(text: str, url: str | None) -> Text:
    label = Text()
    label.append(text, style=f"link {url}" if url is not None else "")

    return label


def issue_url(links: RepoLinks | None, number: str) -> str | None:
    return links.issue(number) if links is not None and number != "" else None


def _normalize_links(text: str) -> str:
    return _OSC8_PARAMS.sub("\x1b]8;;", text)


def _phase_of(story: StoryLine) -> str:
    if story.status == _DRAFT_STATUS:
        return _WIP

    if story.status == _READY_STATUS:
        return _READY

    if story.status == _DONE_STATUS:
        return _DONE

    statuses = {a_slice.status for a_slice in story.slices}
    if statuses == {_MERGED_STATUS} and not _has_pending_learning(story):
        return _DONE

    if statuses <= {_PENDING_STATUS}:
        return _SLICED

    return _WIP


def _has_pending_learning(story: StoryLine) -> bool:
    return any(not lesson.resolved for lesson in _lessons_of(story))


def _lessons_of(story: StoryLine) -> list[LearningLine]:
    return [a_slice.learning for a_slice in story.slices if a_slice.learning is not None] + list(story.lessons)

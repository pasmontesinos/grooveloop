from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.table import Table
from rich.text import Text

from grooveloop.cli.elapsed import format_elapsed
from grooveloop.cli.palette import ERROR, MUTED, OK, WARNING
from grooveloop.shared.domain.tick_outcome import TickOutcome

if TYPE_CHECKING:
    from rich.console import RenderableType

    from grooveloop.shared.application.queries.list_loops import ActivityDTO, LoopDTO, SignalDTO

COLUMN_WIDTH = 46
_TITLE = "LOOPS"
_IDLE_TITLE = "NO LOOP"
_FIRST_TICK_LABEL = "first tick running…"
_OUTCOME_LABELS = {TickOutcome.OK.value: "ok", TickOutcome.FAILED.value: "FAILED"}
_TICK_INDENT = "  "
_ACTIVE_MARK = "▶"
_RUNNING_MARK = "▶"
_ACTIVITY_STYLE = OK
_TITLE_STYLE = "bold"
_ALIVE_STYLE = "bold"
_IDLE_STYLE = MUTED
_FAILED_STYLE = ERROR
_MINUTE = 60
_HOUR = 3600
_MAX_SIGNALS = 4
_REST_LABEL = "+{count} more"
_SIGNAL_ICONS = {"broken": "⛔", "waiting": "⏳"}
_SIGNAL_STYLES = {"broken": ERROR, "waiting": WARNING}
_SIGNAL_LABELS = {
    "failed_tick": "the tick fails",
    "stale_snapshot": "the snapshot is not refreshing",
    "failed_slice": "slice #{reference} in failed",
    "blocked_slice": "slice #{reference} awaits a decision",
    "pull_request_waiting": "PR #{reference} awaits review",
    "blocking_lesson": "slice #{reference} blocked by a lesson",
    "silent_agent": "agent of #{reference} is silent",
}


def title(alive_count: int) -> RenderableType:
    return _split_row(Text(_TITLE, style=_TITLE_STYLE), Text(_alive_count(alive_count)))


def alive_prompt(loop: LoopDTO, *, selected: bool) -> RenderableType:
    lines = [_alive_line(loop, selected), _tick_line(loop)]
    if loop.activity is not None:
        lines.append(_activity_line(loop.activity))

    lines.extend(_signal_lines(loop))

    return Group(*lines)


def idle_heading() -> RenderableType:
    return Text(_IDLE_TITLE, style=_IDLE_STYLE)


def idle_prompt(loop: LoopDTO) -> RenderableType:
    return _split_row(
        Text(loop.repo, style=_IDLE_STYLE),
        Text(format_age(loop.age_seconds), style=_IDLE_STYLE),
    )


def _alive_count(alive_count: int) -> str:
    return f"{alive_count} alive"


def _alive_line(loop: LoopDTO, selected: bool) -> RenderableType:
    mark = _ACTIVE_MARK if selected else " "
    label = Text(f"{mark} ", no_wrap=True)
    label.append(loop.repo, style=_ALIVE_STYLE)

    return _split_row(label, Text(""))


def _tick_line(loop: LoopDTO) -> RenderableType:
    body = Text(_TICK_INDENT, no_wrap=True)
    if loop.tick is None:
        body.append(_FIRST_TICK_LABEL, style=_IDLE_STYLE)

        return _split_row(body, Text(""))

    body.append("tick ", style=_IDLE_STYLE)
    body.append(_outcome_label(loop.tick.outcome), style=_outcome_style(loop.tick.outcome))
    body.append(
        f" · {format_age(loop.tick.age_seconds)} · {format_elapsed(loop.tick.duration_seconds)}",
        style=_IDLE_STYLE,
    )

    return _split_row(body, Text(""))


def _activity_line(activity: ActivityDTO) -> RenderableType:
    body = Text(_TICK_INDENT, no_wrap=True)
    body.append(_RUNNING_MARK, style=_ACTIVITY_STYLE)
    body.append(
        f" {activity.running} {_agent_word(activity.running)}"
        f" · {format_elapsed(activity.elapsed_seconds)}"
        f" · ${activity.cost_usd:.2f}",
        style=_IDLE_STYLE,
    )

    return _split_row(body, Text(""))


def _agent_word(running: int) -> str:
    return "agent" if running == 1 else "agents"


def _signal_lines(loop: LoopDTO) -> list[RenderableType]:
    shown = loop.signals[:_MAX_SIGNALS]
    lines = [_signal_line(signal) for signal in shown]
    rest = len(loop.signals) - len(shown)
    if rest > 0:
        lines.append(_rest_line(rest))

    return lines


def _signal_line(signal: SignalDTO) -> RenderableType:
    body = Text(_TICK_INDENT, no_wrap=True)
    body.append(f"{_SIGNAL_ICONS[signal.category]} {_signal_label(signal)}", style=_SIGNAL_STYLES[signal.category])

    return _split_row(body, Text(""))


def _signal_label(signal: SignalDTO) -> str:
    return _SIGNAL_LABELS[signal.kind].format(reference=signal.reference)


def _rest_line(rest: int) -> RenderableType:
    return _split_row(Text(f"{_TICK_INDENT}{_REST_LABEL.format(count=rest)}", style=_IDLE_STYLE), Text(""))


def _outcome_label(outcome: str) -> str:
    return _OUTCOME_LABELS.get(outcome, outcome)


def _outcome_style(outcome: str) -> str:
    return _FAILED_STYLE if outcome == TickOutcome.FAILED.value else _IDLE_STYLE


def _split_row(left: Text, right: Text) -> RenderableType:
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right")
    grid.add_row(left, right)

    return grid


def format_age(seconds: int) -> str:
    if seconds < _MINUTE:
        return f"{seconds}s ago"

    if seconds < _HOUR:
        return f"{seconds // _MINUTE}m ago"

    return f"{seconds // _HOUR}h ago"

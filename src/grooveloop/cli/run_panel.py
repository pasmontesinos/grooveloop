from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane, Tabs

from grooveloop.cli.elapsed import format_elapsed
from grooveloop.cli.palette import MUTED, OUTCOME_STYLES
from grooveloop.cli.run_log import RunLog
from grooveloop.cli.watch_render import ACTION_MARK, OUTCOME_ICONS, format_tokens

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from grooveloop.cli.watch_render import CostShareLine, ModelLine, SessionLine, SliceLine, ToolTallyLine
    from grooveloop.shared.domain.agent_run_logs import AgentRunLogs

_RUN_TAB = "Run"
_LOG_TAB = "Log"
_LOG_PANE_ID = "run-log"
_SEPARATOR = " · "
_RUNNING_OUTCOME = "running"
_RUN_ID_LENGTH = 8
_NO_VALUE = "—"
_TOKEN_CLASS_LABELS = {
    "input": "input",
    "cache_read": "cache read",
    "cache_write": "cache write",
    "output": "output",
}


class RunSummary(Static):
    pass


class RunPanel(Vertical):
    ALLOW_MAXIMIZE: ClassVar[bool | None] = True
    DEFAULT_CSS = """
    RunPanel { width: 1fr; border: round $border; background: $panel; padding: 0 1; margin: 0 1 0 0; }
    RunPanel.-maximized { width: 1fr; }
    RunPanel RunSummary { padding: 1 0; }
    """

    def __init__(self, logs: AgentRunLogs, *, id: str) -> None:
        super().__init__(id=id)
        self._logs = logs
        self._session: SessionLine | None = None

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane(_RUN_TAB), VerticalScroll():
                yield RunSummary()
            with TabPane(_LOG_TAB, id=_LOG_PANE_ID), VerticalScroll():
                yield RunLog()

    def on_mount(self) -> None:
        self.query_one(Tabs).can_focus = False

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id == _LOG_PANE_ID:
            self._follow_log()

    def show(self, a_slice: SliceLine, session: SessionLine) -> None:
        self._session = session
        self.border_title = f"Run {session.task_type}{_SEPARATOR}slice {a_slice.order}"
        self.query_one(RunSummary).update(_summary(session))
        if self.query_one(TabbedContent).active == _LOG_PANE_ID:
            self._follow_log()

    def _follow_log(self) -> None:
        if self._session is not None:
            self.query_one(RunLog).follow(self._session, self._logs)


def _summary(session: SessionLine) -> Text:
    lines = [
        _heading(session),
        Text(f"run {session.run_id[:_RUN_ID_LENGTH]}{_SEPARATOR}{session.engine}", style=MUTED),
        *[_model_line(model) for model in session.models],
        *_cost_lines(session),
    ]
    if len(session.models) > 0:
        lines.append(Text(f"tokens {_tokens(list(session.models))}"))

    if session.turns is not None:
        lines.append(Text(f"turns {session.turns}{_SEPARATOR}subagents {_or_dash(session.subagents)}"))

    if len(session.tools) > 0:
        lines.append(Text("tools " + _SEPARATOR.join(f"{tool.name} {tool.count}" for tool in _by_use(session))))

    if len(session.skills) > 0:
        lines.append(Text("skills " + _SEPARATOR.join(session.skills)))

    last = _last_action(session)
    if last is not None:
        lines.append(last)

    return Text("\n").join(lines)


def _heading(session: SessionLine) -> Text:
    heading = Text(f"{session.task_type}{_SEPARATOR}{session.profile or _NO_VALUE}{_SEPARATOR}", style="bold")
    heading.append(
        f"{OUTCOME_ICONS[session.outcome]} {format_elapsed(session.elapsed_seconds)}",
        style=OUTCOME_STYLES[session.outcome],
    )
    if session.cause is not None:
        heading.append(f"{_SEPARATOR}{session.cause}", style=OUTCOME_STYLES[session.outcome])

    return heading


def _model_line(model: ModelLine) -> Text:
    return Text(f"{model.model} ${model.cost_usd:.4f} {_tokens([model])}")


def _cost_lines(session: SessionLine) -> list[Text]:
    if session.total_cost_usd is None:
        return [Text(f"cost {_NO_VALUE}", style=MUTED)]

    lines = [Text(f"cost ${session.total_cost_usd:.4f}")]
    lines.extend(_share_line(share, session.total_cost_usd) for share in session.cost_shares)

    return lines


def _share_line(share: CostShareLine, total_cost_usd: float) -> Text:
    label = _TOKEN_CLASS_LABELS[share.token_class]
    if share.cost_usd is None:
        return Text(f"  {label} {_NO_VALUE}", style=MUTED)

    percentage = 100.0 * share.cost_usd / total_cost_usd if total_cost_usd > 0 else 0.0

    return Text(f"  {label} ${share.cost_usd:.4f} {percentage:.0f}%", style=MUTED)


def _tokens(models: list[ModelLine]) -> str:
    cache_read = sum(model.cache_read_tokens for model in models)
    total_input = sum(model.input_tokens + model.cache_read_tokens + model.cache_creation_tokens for model in models)
    cached = 100.0 * cache_read / total_input if total_input > 0 else 0.0
    output = sum(model.output_tokens for model in models)

    return f"↑{format_tokens(total_input)}{_SEPARATOR}{cached:.1f}% cached{_SEPARATOR}↓{format_tokens(output)}"


def _by_use(session: SessionLine) -> list[ToolTallyLine]:
    return sorted(session.tools, key=lambda tool: tool.count, reverse=True)


def _last_action(session: SessionLine) -> Text | None:
    parts: list[str] = []
    if session.last_action is not None:
        parts.append(f"last {ACTION_MARK} {session.last_action}")

    if session.outcome == _RUNNING_OUTCOME and session.silent_seconds is not None:
        parts.append(f"silent {format_elapsed(session.silent_seconds)}")

    if len(parts) == 0:
        return None

    return Text(_SEPARATOR.join(parts))


def _or_dash(value: int | None) -> str:
    return _NO_VALUE if value is None else str(value)

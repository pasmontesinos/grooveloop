from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.widgets import Static

from grooveloop.cli.palette import MUTED, OUTCOME_STYLES
from grooveloop.cli.watch_render import ACTION_MARK, OUTCOME_ICONS

if TYPE_CHECKING:
    from grooveloop.cli.watch_render import SessionLine
    from grooveloop.shared.domain.agent_log_action import AgentLogAction
    from grooveloop.shared.domain.agent_run_logs import AgentRunLogs

_NO_LOG = "no agent.log: the run has not written anything yet"
_NO_ACTIONS = "no actions yet"
_SEPARATOR = " · "
_RESULT_LABELS = {"done": "done", "interrupted": "interrupted", "failed": "failed"}


class RunLog(Static):
    DEFAULT_CSS: ClassVar[str] = """
    RunLog { padding: 1 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._run_id: str | None = None
        self._offset = 0
        self._seen: set[str] = set()
        self._actions: list[AgentLogAction] = []

    def follow(self, session: SessionLine, logs: AgentRunLogs) -> None:
        if session.run_id != self._run_id:
            self._restart(session.run_id)

        chunk = logs.read(session.run_id, self._offset)
        if chunk is None:
            self._restart(session.run_id)
            self.update(Text(_NO_LOG, style=MUTED))

            return

        for action in chunk.actions:
            self._add(action)
        self._offset = chunk.offset

        self.update(_timeline(self._actions, session))

    def _restart(self, run_id: str) -> None:
        self._run_id = run_id
        self._offset = 0
        self._seen = set()
        self._actions = []

    def _add(self, action: AgentLogAction) -> None:
        if action.tool_use_id is not None:
            if action.tool_use_id in self._seen:
                return
            self._seen.add(action.tool_use_id)

        self._actions.append(action)


def _timeline(actions: list[AgentLogAction], session: SessionLine) -> Text:
    lines = [Text(f"{ACTION_MARK} {action.description}") for action in actions]
    if len(lines) == 0:
        lines.append(Text(_NO_ACTIONS, style=MUTED))

    if session.outcome in _RESULT_LABELS:
        lines.append(Text(_result(session), style=OUTCOME_STYLES[session.outcome]))

    return Text("\n").join(lines)


def _result(session: SessionLine) -> str:
    result = f"{OUTCOME_ICONS[session.outcome]} result: {_RESULT_LABELS[session.outcome]}"
    if session.cause is None:
        return result

    return f"{result}{_SEPARATOR}{session.cause}"

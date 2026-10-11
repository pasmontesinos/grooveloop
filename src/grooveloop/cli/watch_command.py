from __future__ import annotations

import sys

from grooveloop.bootstrap import container
from grooveloop.cli.palette import WATCH_THEME
from grooveloop.cli.watch_app import LoopsApp, has_terminal
from grooveloop.cli.watch_render import DEFAULT_STALL_AFTER_SECONDS
from grooveloop.shared.application.queries.list_loops import ListLoopsQueryHandler
from grooveloop.shared.application.queries.query_bus import QueryBus
from grooveloop.shared.domain.agent_run_logs import AgentRunLogs
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
from grooveloop.shared.domain.pull_request_details import PullRequestDetails
from grooveloop.shared.domain.story_specs import StorySpecs
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode

_NO_TERMINAL_MESSAGE = "watch needs an interactive terminal"


def run(*, interval: int = 1, stall_after: int = DEFAULT_STALL_AFTER_SECONDS, screenshot: str | None = None) -> int:
    if screenshot is None and not has_terminal():
        print(_NO_TERMINAL_MESSAGE, file=sys.stderr)

        return ExitCode.USAGE_ERROR

    handler = container.get(ListLoopsQueryHandler)
    snapshots = container.get(LoopSnapshots)
    details = container.get(PullRequestDetails)
    logs = container.get(AgentRunLogs)
    specs = container.get(StorySpecs)
    query_bus = container.get(QueryBus)
    clock = container.get(Clock)

    app = LoopsApp(
        handler, snapshots, details, logs, specs, query_bus, clock, interval=interval, stall_after=stall_after
    )
    app.register_theme(WATCH_THEME)
    app.theme = WATCH_THEME.name
    if screenshot is not None:
        return app.capture(screenshot)

    return app.run() or ExitCode.OK

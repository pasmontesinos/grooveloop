from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.cli.preflight import run_preflight
from grooveloop.shared.infrastructure.agent_workdir import AgentWorkdir
from grooveloop.shared.infrastructure.cli.exit_code import ExitCode
from grooveloop.shared.infrastructure.target_repo import TargetRepo


def run(workdir: str = ".", repo: str | None = None) -> int:
    container.bind(AgentWorkdir, AgentWorkdir(workdir))
    if repo is not None:
        container.bind(TargetRepo, TargetRepo(repo))

    report = run_preflight(with_merger=repo is not None)

    for outcome in report.outcomes:
        print(outcome.line())

    return ExitCode.OK if report.passed() else ExitCode.FAILURE

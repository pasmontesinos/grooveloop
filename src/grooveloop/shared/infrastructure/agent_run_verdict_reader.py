from __future__ import annotations

import json
from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.infrastructure.agent_exit_marker import is_stalled, is_vanished, read_exit_code
from grooveloop.shared.infrastructure.log_tail import read_log_tail

if TYPE_CHECKING:
    from pathlib import Path

    from grooveloop.shared.domain.agent_log_reader import AgentLogReader

_METADATA_FILE = "run.json"
_LOG_FILE = "agent.log"
_DEFAULT_ENGINE = "claude"
_TAIL_LINES = 5
_TAIL_BYTES = 262_144


def read_run_verdict(run_dir: Path, engine: str, log_readers: dict[str, AgentLogReader]) -> AgentRunVerdict:
    log = run_dir / _LOG_FILE
    if not log.is_file():
        return AgentRunVerdict(AgentOutcome.RUNNING)

    exit_code = read_exit_code(log)
    if exit_code is None:
        return AgentRunVerdict(AgentOutcome.RUNNING)

    if exit_code == 0:
        return AgentRunVerdict(AgentOutcome.SUCCEEDED)

    if is_stalled(log):
        return AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.STALLED)

    if is_vanished(log):
        return AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.VANISHED)

    reader = log_readers.get(engine)
    if reader is None:
        return AgentRunVerdict(AgentOutcome.FAILED, AgentRunCause.UNKNOWN)

    return reader.verdict("\n".join(read_log_tail(log, _TAIL_LINES, _TAIL_BYTES)), exit_code)


def read_run_engine(run_dir: Path) -> str:
    metadata = run_dir / _METADATA_FILE
    if not metadata.is_file():
        return _DEFAULT_ENGINE

    return str(json.loads(metadata.read_text()).get("engine", _DEFAULT_ENGINE))

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from grooveloop.shared.domain.agent_log_chunk import AgentLogChunk
from grooveloop.shared.domain.agent_run_logs import AgentRunLogs

if TYPE_CHECKING:
    from pathlib import Path

    from grooveloop.shared.domain.agent_log_reader import AgentLogReader

_METADATA_FILE = "run.json"
_LOG_FILE = "agent.log"
_DEFAULT_ENGINE = "claude"
_NEWLINE = b"\n"


class FilesystemAgentRunLogs(AgentRunLogs):
    def __init__(self, runs_dir: Path, log_readers: dict[str, AgentLogReader]) -> None:
        self._runs_dir = runs_dir
        self._log_readers = log_readers

    def read(self, run_id: str, offset: int) -> AgentLogChunk | None:
        run_dir = self._runs_dir / run_id
        log = run_dir / _LOG_FILE
        if not log.is_file():
            return None

        with log.open("rb") as stream:
            stream.seek(offset)
            written = stream.read()

        complete = written[: written.rfind(_NEWLINE) + 1]
        reader = self._log_readers.get(self._engine(run_dir))
        text = complete.decode("utf-8", errors="replace")

        return AgentLogChunk(actions=reader.actions(text) if reader is not None else [], offset=offset + len(complete))

    def _engine(self, run_dir: Path) -> str:
        metadata = run_dir / _METADATA_FILE
        if not metadata.is_file():
            return _DEFAULT_ENGINE

        return str(json.loads(metadata.read_text()).get("engine", _DEFAULT_ENGINE))

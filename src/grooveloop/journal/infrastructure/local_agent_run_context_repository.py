from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from grooveloop.journal.domain.agent_run_context import AgentRunContext
from grooveloop.journal.domain.agent_run_context_repository import AgentRunContextRepository

if TYPE_CHECKING:
    from pathlib import Path

    from grooveloop.journal.domain.agent_run_id import AgentRunId

_METADATA_FILE = "run.json"


class LocalAgentRunContextRepository(AgentRunContextRepository):
    def __init__(self, runs_dir: Path) -> None:
        self._runs_dir = runs_dir

    def find(self, id: AgentRunId) -> AgentRunContext | None:
        metadata_path = self._runs_dir / id.value / _METADATA_FILE
        if not metadata_path.is_file():
            return None

        data = json.loads(metadata_path.read_text())
        story_id = data.get("story_id")
        if story_id is None:
            return None

        return AgentRunContext(
            repo=data["repo"],
            story_id=story_id,
            profile=data["profile"],
            started_at=datetime.fromisoformat(data["started_at"]),
        )

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_log_reader import AgentLogReader


@dataclass(frozen=True)
class AgentLogReaders:
    value: dict[str, AgentLogReader]

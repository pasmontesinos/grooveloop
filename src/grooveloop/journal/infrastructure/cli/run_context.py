from __future__ import annotations

import os
from typing import TYPE_CHECKING

from grooveloop.bootstrap import container
from grooveloop.journal.domain.agent_run_context_repository import AgentRunContextRepository
from grooveloop.journal.domain.agent_run_id import AgentRunId

if TYPE_CHECKING:
    from grooveloop.journal.domain.agent_run_context import AgentRunContext

_RUN_ID_ENV_VAR = "GROOVELOOP_RUN_ID"


def resolve_current_run_context() -> AgentRunContext | None:
    run_id = os.environ.get(_RUN_ID_ENV_VAR)
    if run_id is None:
        return None

    repository = container.get(AgentRunContextRepository)
    context: AgentRunContext | None = repository.find(AgentRunId(run_id))

    return context

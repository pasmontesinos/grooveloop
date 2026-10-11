from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from grooveloop.shared.domain.agent_outcome import AgentOutcome
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
from grooveloop.shared.infrastructure.agent_exit_marker import is_terminated

_RESULT_EVENT = "result"
_SYSTEM_EVENT = "system"
_API_RETRY_SUBTYPE = "api_retry"
_SERVER_ERROR_STATUSES = range(500, 600)


@dataclass(frozen=True)
class _Signature:
    verdict: AgentRunVerdict
    statuses: list[int]
    errors: list[str]
    prefixes: list[str]

    def matches(self, status: int | None, error: str, text: str) -> bool:
        return (
            status in self.statuses or error in self.errors or any(text.startswith(prefix) for prefix in self.prefixes)
        )


_SIGNATURES = [
    _Signature(
        AgentRunVerdict(AgentOutcome.FAILED, AgentRunCause.AUTH),
        statuses=[401],
        errors=["authentication_failed"],
        prefixes=["Failed to authenticate"],
    ),
    _Signature(
        AgentRunVerdict(AgentOutcome.FAILED, AgentRunCause.RATE_LIMIT),
        statuses=[429],
        errors=["rate_limit"],
        prefixes=["You've hit your session limit"],
    ),
    _Signature(
        AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.OVERLOADED),
        statuses=[529],
        errors=["overloaded"],
        prefixes=["API Error: 529"],
    ),
    _Signature(
        AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.SERVER_ERROR),
        statuses=list(_SERVER_ERROR_STATUSES),
        errors=["server_error"],
        prefixes=["API Error: Server error"],
    ),
    _Signature(
        AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.NETWORK),
        statuses=[],
        errors=[],
        prefixes=[
            "API Error: Can't reach the API server",
            "API Error: Connection closed",
            "API Error: Connection lost",
            "API Error: Your computer went to sleep",
        ],
    ),
]
_UNKNOWN = AgentRunVerdict(AgentOutcome.FAILED, AgentRunCause.UNKNOWN)
_TERMINATED = AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.TERMINATED)
_CRASHED = AgentRunVerdict(AgentOutcome.INTERRUPTED, AgentRunCause.CRASHED)


def parse_run_verdict(log_tail: str, exit_code: int) -> AgentRunVerdict:
    event = _last_event(log_tail)
    if event is not None and event.get("type") == _RESULT_EVENT:
        return _classify(event.get("api_error_status"), "", str(event.get("result", "")))

    if event is not None and event.get("type") == _SYSTEM_EVENT and event.get("subtype") == _API_RETRY_SUBTYPE:
        verdict = _classify(event.get("error_status"), str(event.get("error", "")), "")
        if verdict != _UNKNOWN:
            return verdict

    return _TERMINATED if is_terminated(exit_code) else _CRASHED


def _classify(status: Any, error: str, text: str) -> AgentRunVerdict:
    code = status if isinstance(status, int) else None
    for signature in _SIGNATURES:
        if signature.matches(code, error, text):
            return signature.verdict

    return _UNKNOWN


def _last_event(log_tail: str) -> dict[str, Any] | None:
    for line in reversed(log_tail.splitlines()):
        event = _load(line)
        if isinstance(event, dict):
            return event

    return None


def _load(line: str) -> Any:
    try:
        return json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

from __future__ import annotations

from enum import Enum


class AgentRunCause(Enum):
    EMPTY = None
    OVERLOADED = "overloaded"
    SERVER_ERROR = "server_error"
    NETWORK = "network"
    TERMINATED = "terminated"
    CRASHED = "crashed"
    VANISHED = "vanished"
    STALLED = "stalled"
    INCOMPLETE = "incomplete"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"

from __future__ import annotations

from enum import StrEnum


class LoopSignalKind(StrEnum):
    FAILED_TICK = "failed_tick"
    STALE_SNAPSHOT = "stale_snapshot"
    FAILED_SLICE = "failed_slice"
    BLOCKED_SLICE = "blocked_slice"
    PULL_REQUEST_WAITING = "pull_request_waiting"
    BLOCKING_LESSON = "blocking_lesson"
    SILENT_AGENT = "silent_agent"

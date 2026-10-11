from __future__ import annotations

from enum import StrEnum


class Mergeability(StrEnum):
    BEHIND = "behind"
    BLOCKED = "blocked"
    CLEAN = "clean"
    DIRTY = "dirty"
    DRAFT = "draft"
    HAS_HOOKS = "has_hooks"
    UNKNOWN = "unknown"
    UNSTABLE = "unstable"

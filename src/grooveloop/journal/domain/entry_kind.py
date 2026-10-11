from __future__ import annotations

from enum import StrEnum


class EntryKind(StrEnum):
    CONSTRAINT = "constraint"
    DIRECTIVE = "directive"
    DECISION = "decision"
    FINDING = "finding"

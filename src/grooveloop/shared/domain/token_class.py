from __future__ import annotations

from enum import StrEnum


class TokenClass(StrEnum):
    INPUT = "input"
    CACHE_READ = "cache_read"
    CACHE_WRITE = "cache_write"
    OUTPUT = "output"

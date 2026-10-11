from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    FAILURE = 1
    USAGE_ERROR = 2
    PREFLIGHT_FAILED = 3
    MISSING_CONTEXT = 4


def describe_exit_codes(descriptions: dict[ExitCode, str]) -> str:
    lines = [f"  {code.value}  {description}" for code, description in descriptions.items()]

    return "\n".join(["Exit codes:", *lines])

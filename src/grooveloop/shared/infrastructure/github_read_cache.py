from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from grooveloop.shared.domain.clock import Clock

T = TypeVar("T")


class GithubReadCache:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[datetime, object]] = {}

    def get_or_load(self, key: str, loader: Callable[[], T], ttl: int) -> T:
        now = self._clock.now()
        entry = self._entries.get(key)

        if entry is not None and (now - entry[0]).total_seconds() < ttl:
            return cast("T", entry[1])

        value = loader()
        self._entries[key] = (now, value)

        return value

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        for key in [key for key in self._entries if key.startswith(prefix)]:
            self._entries.pop(key, None)

    def flush(self) -> None:
        self._entries.clear()

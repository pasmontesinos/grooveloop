from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest

from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache


def _load(calls: list[int]) -> int:
    calls.append(1)

    return len(calls)


@pytest.fixture
def clock() -> Any:
    return create_autospec(Clock, spec_set=True, instance=True)


@pytest.mark.integration
class TestGithubReadCache:
    def test_loads_on_miss_and_serves_cached_value_within_ttl(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
        cache = GithubReadCache(clock)
        calls: list[int] = []

        first = cache.get_or_load("k", lambda: _load(calls), 300)
        second = cache.get_or_load("k", lambda: _load(calls), 300)

        assert first == second
        assert len(calls) == 1

    def test_reloads_after_ttl_expires(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
        cache = GithubReadCache(clock)
        calls: list[int] = []
        cache.get_or_load("k", lambda: _load(calls), 300)

        clock.now.return_value = datetime(2026, 6, 1, 0, 5, 0, tzinfo=UTC)
        cache.get_or_load("k", lambda: _load(calls), 300)

        assert len(calls) == 2

    def test_flush_forces_a_reload(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
        cache = GithubReadCache(clock)
        calls: list[int] = []
        cache.get_or_load("k", lambda: _load(calls), 300)

        cache.flush()
        cache.get_or_load("k", lambda: _load(calls), 300)

        assert len(calls) == 2

    def test_caches_each_key_separately(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
        cache = GithubReadCache(clock)
        calls: list[int] = []

        cache.get_or_load("a", lambda: _load(calls), 300)
        cache.get_or_load("b", lambda: _load(calls), 300)

        assert len(calls) == 2

    def test_invalidate_forces_a_reload_of_the_key(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
        cache = GithubReadCache(clock)
        calls: list[int] = []
        cache.get_or_load("k", lambda: _load(calls), 300)

        cache.invalidate("k")
        cache.get_or_load("k", lambda: _load(calls), 300)

        assert len(calls) == 2

    def test_invalidate_leaves_other_keys_cached(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
        cache = GithubReadCache(clock)
        calls: list[int] = []
        cache.get_or_load("a", lambda: _load(calls), 300)
        cache.get_or_load("b", lambda: _load(calls), 300)

        cache.invalidate("a")
        cache.get_or_load("b", lambda: _load(calls), 300)

        assert len(calls) == 2

    def test_invalidate_is_a_noop_for_an_absent_key(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
        cache = GithubReadCache(clock)

        cache.invalidate("missing")

    def test_invalidate_prefix_forces_a_reload_of_every_matching_key(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
        cache = GithubReadCache(clock)
        calls: list[int] = []
        cache.get_or_load("issues:open", lambda: _load(calls), 300)
        cache.get_or_load("issues:open:grooveloop", lambda: _load(calls), 300)

        cache.invalidate_prefix("issues:")
        cache.get_or_load("issues:open", lambda: _load(calls), 300)
        cache.get_or_load("issues:open:grooveloop", lambda: _load(calls), 300)

        assert len(calls) == 4

    def test_invalidate_prefix_leaves_non_matching_keys_cached(self, clock: Mock) -> None:
        clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
        cache = GithubReadCache(clock)
        calls: list[int] = []
        cache.get_or_load("issue:7", lambda: _load(calls), 300)

        cache.invalidate_prefix("issues:")
        cache.get_or_load("issue:7", lambda: _load(calls), 300)

        assert len(calls) == 1

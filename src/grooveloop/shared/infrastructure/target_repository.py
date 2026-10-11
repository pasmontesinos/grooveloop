from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from github import Github
    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
    from grooveloop.shared.infrastructure.target_repo import TargetRepo

_TTL_SECONDS = 300
_KEY_PREFIX = "repo:"


def target_repository(github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> Repository:
    return cache.get_or_load(
        f"{_KEY_PREFIX}{target_repo.value}", lambda: github.get_repo(target_repo.value), _TTL_SECONDS
    )

from __future__ import annotations

from typing import Any
from unittest.mock import create_autospec

from github import Github
from github.Repository import Repository


def github_client_for_any_repo() -> Any:
    github = create_autospec(Github, spec_set=True, instance=True)
    github.get_repo.return_value = create_autospec(Repository, spec_set=True, instance=True)

    return github

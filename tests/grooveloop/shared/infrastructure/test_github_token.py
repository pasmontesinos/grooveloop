from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from grooveloop.shared.infrastructure.github_token import GithubTokenError, github_token


@pytest.mark.integration
class TestGithubToken:
    def test_should_return_the_token_from_gh(self) -> None:
        with patch("grooveloop.shared.infrastructure.github_token.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=["gh", "auth", "token"], returncode=0, stdout="gho_abc123\n"
            )

            assert github_token() == "gho_abc123"

    def test_should_raise_when_gh_is_not_authenticated(self) -> None:
        with patch(
            "grooveloop.shared.infrastructure.github_token.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["gh", "auth", "token"]),
        ):
            with pytest.raises(GithubTokenError):
                github_token()

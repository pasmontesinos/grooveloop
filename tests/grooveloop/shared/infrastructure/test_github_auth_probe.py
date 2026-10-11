from __future__ import annotations

from typing import Any
from unittest.mock import create_autospec

import pytest
from github import Github
from github.AuthenticatedUser import AuthenticatedUser
from github.GithubException import GithubException

from grooveloop.shared.infrastructure.github_auth_probe import GithubAuthProbe


@pytest.mark.integration
class TestGithubAuthProbe:
    def test_check_should_pass_when_the_token_authenticates(self) -> None:
        github = create_autospec(Github, spec_set=True, instance=True)
        user = create_autospec(AuthenticatedUser, spec_set=True, instance=True)
        user.login = "octocat"
        github.get_user.return_value = user
        probe = GithubAuthProbe(github)

        probe.check()

        github.get_user.assert_called_once_with()

    def test_check_should_raise_when_authentication_fails(self) -> None:
        github: Any = create_autospec(Github, spec_set=True, instance=True)
        github.get_user.side_effect = GithubException(401, {}, {})
        probe = GithubAuthProbe(github)

        with pytest.raises(GithubException):
            probe.check()

    def test_should_expose_a_name(self) -> None:
        assert GithubAuthProbe(create_autospec(Github, spec_set=True, instance=True)).name == "github-auth"

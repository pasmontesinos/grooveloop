from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.application.probes.probe import Probe

if TYPE_CHECKING:
    from github import Github


class GithubAuthProbe(Probe):
    name = "github-auth"

    def __init__(self, github: Github) -> None:
        self._github = github

    def check(self) -> None:
        _ = self._github.get_user().login

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.File import File
from github.PullRequest import PullRequest
from github.Repository import Repository

from grooveloop.shared.domain.pull_request_file import PullRequestFile
from grooveloop.shared.infrastructure.github_pull_request_contents import (
    GithubPullRequestContents,
    PullRequestContents,
)


def _file(filename: str, patch: str | None) -> Any:
    file = create_autospec(File, spec_set=True, instance=True)
    file.filename = filename
    file.status = "modified"
    file.additions = 3
    file.deletions = 1
    file.patch = patch

    return file


def _repo_with_pull(body: str | None, *files: Any) -> Any:
    pull = create_autospec(PullRequest, spec_set=True, instance=True)
    pull.body = body
    pull.get_files.return_value = list(files)
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.get_pull.return_value = pull

    return repo


@pytest.mark.integration
class TestGithubPullRequestContents:
    def test_should_read_the_body_and_every_file_of_the_pull_request(self) -> None:
        repo = _repo_with_pull("## Summary", _file("src/x.py", "@@ -1 +1 @@"), _file("logo.png", None))

        contents = GithubPullRequestContents(repo).read(2115)

        repo.get_pull.assert_called_once_with(2115)
        assert contents == PullRequestContents(
            body="## Summary",
            files=[
                PullRequestFile(filename="src/x.py", status="modified", additions=3, deletions=1, patch="@@ -1 +1 @@"),
                PullRequestFile(filename="logo.png", status="modified", additions=3, deletions=1, patch=None),
            ],
        )

    def test_should_read_an_empty_body_when_the_pull_request_has_none(self) -> None:
        repo: Mock = _repo_with_pull(None)

        assert GithubPullRequestContents(repo).read(2115).body == ""

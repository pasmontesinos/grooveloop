from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.domain.pull_request_file import PullRequestFile

if TYPE_CHECKING:
    from github.File import File
    from github.Repository import Repository


@dataclass(frozen=True)
class PullRequestContents:
    body: str
    files: list[PullRequestFile]


class GithubPullRequestContents:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def read(self, number: int) -> PullRequestContents:
        pull = self._repo.get_pull(number)

        return PullRequestContents(body=pull.body or "", files=[_file_of(file) for file in pull.get_files()])


def _file_of(file: File) -> PullRequestFile:
    return PullRequestFile(
        filename=file.filename,
        status=file.status,
        additions=file.additions,
        deletions=file.deletions,
        patch=file.patch,
    )

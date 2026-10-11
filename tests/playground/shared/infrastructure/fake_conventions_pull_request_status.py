from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.conventions_pull_request_status import ConventionsPullRequestStatus

if TYPE_CHECKING:
    from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest


class FakeConventionsPullRequestStatus(ConventionsPullRequestStatus):
    def __init__(self, open_pull_requests: set[int] | None = None) -> None:
        self._open_pull_requests = open_pull_requests or set()

    def is_open(self, conventions_pull_request: ConventionsPullRequest) -> bool:
        return conventions_pull_request.value in self._open_pull_requests

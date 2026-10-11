from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.domain.pull_request_detail_reading import PullRequestDetailReading
from grooveloop.shared.domain.pull_request_detail_state import PullRequestDetailState
from grooveloop.shared.domain.pull_request_details import PullRequestDetails

if TYPE_CHECKING:
    from grooveloop.shared.domain.pull_request_detail import PullRequestDetail


class FakePullRequestDetails(PullRequestDetails):
    def __init__(self, details: list[PullRequestDetail] | None = None, unreadable: list[int] | None = None) -> None:
        self.published: list[PullRequestDetail] = []
        self._details = {detail.number: detail for detail in (details or [])}
        self._unreadable = unreadable or []

    def publish(self, repo: str, detail: PullRequestDetail) -> None:
        self.published.append(detail)
        self._details[detail.number] = detail

    def find(self, repo: str, number: int) -> PullRequestDetail | None:
        return self._details.get(number)

    def read(self, repo: str, number: int) -> PullRequestDetailReading:
        if number in self._unreadable:
            return PullRequestDetailReading(state=PullRequestDetailState.UNREADABLE)

        detail = self._details.get(number)
        if detail is None:
            return PullRequestDetailReading(state=PullRequestDetailState.MISSING)

        return PullRequestDetailReading(state=PullRequestDetailState.SYNCED, detail=detail)

    def retain(self, repo: str, numbers: list[int]) -> None:
        self._details = {number: detail for number, detail in self._details.items() if number in numbers}

    def numbers(self) -> list[int]:
        return sorted(self._details)

from __future__ import annotations

from typing import TYPE_CHECKING

from github import UnknownObjectException

from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.infrastructure.github_review_verdict_labels import VERDICT_LABELS

if TYPE_CHECKING:
    from github.Repository import Repository

_LABEL_COLOR = "ededed"
_LABELS = [*VERDICT_LABELS, *[status.value for status in SliceStatus]]


class GithubDeliveryLabels:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def ensure(self) -> None:
        for name in _LABELS:
            if self._missing(name):
                self._repo.create_label(name, _LABEL_COLOR)

    def _missing(self, name: str) -> bool:
        try:
            self._repo.get_label(name)
        except UnknownObjectException:
            return True

        return False

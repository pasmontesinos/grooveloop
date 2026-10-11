from __future__ import annotations

from typing import TYPE_CHECKING

from github import UnknownObjectException

from grooveloop.delivery.domain.slice_labels import SliceLabels

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.delivery.domain.slice_id import SliceId

_LABEL_COLOR = "ededed"


class GithubSliceLabels(SliceLabels):
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def ensure(self, slice_id: SliceId) -> None:
        name = f"slice:{slice_id.value}"
        try:
            self._repo.get_label(name)
        except UnknownObjectException:
            self._repo.create_label(name, _LABEL_COLOR)

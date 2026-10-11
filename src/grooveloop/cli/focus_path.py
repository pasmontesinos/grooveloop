from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.widgets import Static

if TYPE_CHECKING:
    from grooveloop.cli.watch_render import SliceLine, StoryLine

_SEPARATOR = " \u203a "


class FocusPath(Static):
    DEFAULT_CSS = """
    FocusPath { height: 1; padding: 0 2; background: $panel; }
    """

    def show(self, repo: str | None, story: StoryLine | None, a_slice: SliceLine | None) -> None:
        parts: list[str] = []
        if repo is not None:
            parts.append(repo)

        if story is not None:
            parts.append(f"#{story.number} {story.title}")

        if a_slice is not None:
            parts.append(f"{a_slice.order} {a_slice.title}")

        self.update(Text(_SEPARATOR.join(parts)))

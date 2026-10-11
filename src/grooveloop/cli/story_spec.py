from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import VerticalScroll
from textual.widgets import Markdown

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from grooveloop.shared.domain.story_spec_reading import StorySpecReading

_MISSING_SPEC = "waiting for the next tick"


class StorySpecBody(Markdown):
    pass


class StorySpec(VerticalScroll):
    DEFAULT_CSS = """
    StorySpec StorySpecBody { padding: 0 1; }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._reading: StorySpecReading | None = None

    def compose(self) -> ComposeResult:
        yield StorySpecBody(_MISSING_SPEC, open_links=False)

    def show(self, reading: StorySpecReading | None) -> None:
        if reading == self._reading:
            return

        self._reading = reading
        self.query_one(StorySpecBody).update(reading.spec if reading is not None else _MISSING_SPEC)

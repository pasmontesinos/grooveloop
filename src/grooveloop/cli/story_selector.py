from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from textual.widgets import Select

if TYPE_CHECKING:
    from textual.widget import Widget

    from grooveloop.cli.watch_render import StoryLine

_NO_STORY = ""
_TITLE_WIDTH = 32
_ELLIPSIS = "…"
_RUNNING_STATUSES = ("dispatched", "under_review", "changes_requested")
_WAITING_STATUSES = ("pr_open",)
_STOPPED_STATUSES = ("blocked", "failed")
_RUNNING_MARK = "▶"
_WAITING_MARK = "⏳"
_STOPPED_MARK = "⛔"


class StorySelector(Select[str], can_focus=False):
    DEFAULT_CSS = """
    StorySelector { display: none; margin: 1 0 0 0; }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__([("", _NO_STORY)], allow_blank=False, compact=True, id=id)
        self._shown: list[tuple[str, str]] = []
        self._focused_before_expanding: Widget | None = None

    @property
    def chosen_story(self) -> str | None:
        return self.selection or None

    def show_stories(self, stories: list[StoryLine], chosen: str | None) -> None:
        self.display = len(stories) > 0
        options = [(story_label(story), story.number) for story in stories]
        relabelled = len(options) > 0 and options != self._shown
        self._shown = options
        if relabelled:
            self.set_options(options)

        if chosen is not None:
            self.value = chosen

        if relabelled:
            self.mutate_reactive(StorySelector.value)  # type: ignore[misc]

    def choose_neighbour(self, step: int) -> None:
        numbers = [number for _, number in self._shown]
        if self.selection not in numbers:
            return

        self.value = numbers[(numbers.index(self.selection) + step) % len(numbers)]

    def validate_expanded(self, expanded: bool) -> bool:
        if expanded and not self.expanded:
            self._focused_before_expanding = self.screen.focused

        return expanded and len(self._shown) > 1

    def watch_expanded(self, expanded: bool) -> None:
        focused = self._focused_before_expanding
        if expanded or focused is None:
            return

        self._focused_before_expanding = None
        current = self.screen.focused
        if focused.is_attached and (current is None or self in current.ancestors_with_self):
            focused.focus()


def story_label(story: StoryLine) -> str:
    return f"#{story.number} {_shortened(story.title)}{_signal(story)}"


def _shortened(title: str) -> str:
    if len(title) <= _TITLE_WIDTH:
        return title

    return title[: _TITLE_WIDTH - len(_ELLIPSIS)] + _ELLIPSIS


def _signal(story: StoryLine) -> str:
    counts = Counter(a_slice.status for a_slice in story.slices)
    running = sum(counts[status] for status in _RUNNING_STATUSES)
    marks = []
    if running > 0:
        marks.append(f"{_RUNNING_MARK}{running}")

    if any(counts[status] > 0 for status in _WAITING_STATUSES):
        marks.append(_WAITING_MARK)

    if any(counts[status] > 0 for status in _STOPPED_STATUSES):
        marks.append(_STOPPED_MARK)

    return "".join(f" {mark}" for mark in marks)

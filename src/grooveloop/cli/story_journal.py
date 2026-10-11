from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.content import Content
from textual.message import Message
from textual.widgets import Markdown, Static

from grooveloop.cli.loops_render import format_age
from grooveloop.cli.palette import FOCUS, MUTED

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from grooveloop.shared.application.queries.read_journal_entries import JournalEntryDTO

_KINDS = ["constraint", "directive", "decision", "finding"]
_FILTER_LABEL = "filter: "
_SEPARATOR = " · "


class JournalFilter(Static):
    class KindToggled(Message):
        def __init__(self, kind: str) -> None:
            super().__init__()
            self.kind = kind

    def choose(self, chosen: str | None) -> None:
        self.update(_filter_line(chosen))

    def action_toggle_kind(self, kind: str) -> None:
        self.post_message(JournalFilter.KindToggled(kind))


class JournalEntryHeader(Static):
    pass


class JournalEntryBody(Markdown):
    pass


class JournalEntryBlock(Vertical):
    def __init__(self, entry: JournalEntryDTO, now: datetime, *, shown: bool) -> None:
        super().__init__()
        self._entry = entry
        self._header = JournalEntryHeader(_header(entry, now))
        self.display = shown

    @property
    def kind(self) -> str:
        return self._entry.kind

    def compose(self) -> ComposeResult:
        yield self._header
        yield JournalEntryBody(self._entry.body, open_links=False)

    def show_age(self, now: datetime) -> None:
        self._header.update(_header(self._entry, now))


class JournalEntries(VerticalScroll):
    pass


class StoryJournal(Vertical):
    DEFAULT_CSS = """
    StoryJournal JournalFilter { padding: 0 1; }
    StoryJournal JournalEntryBlock { height: auto; }
    StoryJournal JournalEntryHeader { padding: 1 1 0 1; }
    StoryJournal JournalEntryBody { padding: 0 1; border-left: heavy $secondary; margin: 0 1; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [Binding("f", "next_kind", "filter")]

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._entries: list[JournalEntryDTO] | None = None
        self._kind: str | None = None

    def compose(self) -> ComposeResult:
        yield JournalFilter(_filter_line(None))
        yield JournalEntries()

    def show(self, entries: list[JournalEntryDTO], now: datetime) -> None:
        if entries == self._entries:
            for block in self.query(JournalEntryBlock).results(JournalEntryBlock):
                block.show_age(now)

            return

        self._entries = entries
        scroll = self.query_one(JournalEntries)
        scroll.remove_children()
        scroll.mount_all([JournalEntryBlock(entry, now, shown=self._shows(entry.kind)) for entry in entries])

    def show_latest(self) -> None:
        self.query_one(JournalEntries).anchor()

    def action_next_kind(self) -> None:
        position = _KINDS.index(self._kind) + 1 if self._kind is not None else 0
        self._choose(_KINDS[position] if position < len(_KINDS) else None)

    def on_journal_filter_kind_toggled(self, message: JournalFilter.KindToggled) -> None:
        self._choose(None if message.kind == self._kind else message.kind)

    def _choose(self, kind: str | None) -> None:
        self._kind = kind
        self.query_one(JournalFilter).choose(kind)
        for block in self.query(JournalEntryBlock).results(JournalEntryBlock):
            block.display = self._shows(block.kind)

    def _shows(self, kind: str) -> bool:
        return self._kind is None or kind == self._kind


def _filter_line(chosen: str | None) -> Content:
    kinds = [_filter_kind(kind, chosen=kind == chosen) for kind in _KINDS]

    return Content.from_markup(f"[{MUTED}]{_FILTER_LABEL}[/]{_SEPARATOR.join(kinds)}")


def _filter_kind(kind: str, *, chosen: bool) -> str:
    style = "bold reverse " if chosen else ""

    return f"[{style}@click=toggle_kind('{kind}')]{kind}[/]"


def _header(entry: JournalEntryDTO, now: datetime) -> Text:
    age = format_age(int((now - datetime.fromisoformat(entry.written_at)).total_seconds()))

    return Text(_SEPARATOR).join(
        [Text(age, style=MUTED), Text(entry.kind, style=FOCUS), Text(entry.author, style="bold")]
    )

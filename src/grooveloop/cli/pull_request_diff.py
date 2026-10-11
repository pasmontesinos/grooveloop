from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.syntax import Syntax
from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import OptionList, Static

from grooveloop.cli.palette import ERROR, MUTED, OK, WARNING

if TYPE_CHECKING:
    from rich.console import RenderableType
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from grooveloop.shared.domain.pull_request_file import PullRequestFile

_NO_FILES = "no files"
_NO_PATCH = "GitHub did not send the patch (binary or too large): press o to open the PR on GitHub"
_MINUS = "\u2212"


class PullRequestFiles(OptionList):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("enter", "app.expand_detail", "expand", show=False)]


class PullRequestPatch(Static):
    pass


class PullRequestDiff(Vertical):
    DEFAULT_CSS = """
    PullRequestDiff PullRequestFiles { height: auto; max-height: 10; border: none; }
    PullRequestDiff VerticalScroll { height: 1fr; }
    PullRequestDiff PullRequestPatch { padding: 1 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._files: list[PullRequestFile] | None = None

    def compose(self) -> ComposeResult:
        yield PullRequestFiles()
        with VerticalScroll():
            yield PullRequestPatch()

    def show(self, files: list[PullRequestFile] | None) -> None:
        if files == self._files:
            return

        options = self.query_one(PullRequestFiles)
        chosen = self._chosen_file()
        self._files = files
        options.set_options(_option(a_file) for a_file in files or [])
        options.highlighted = _index(files or [], chosen)
        self._show_patch()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self._show_patch()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._show_patch()

    def _chosen_file(self) -> str | None:
        a_file = self._highlighted_file()

        return a_file.filename if a_file is not None else None

    def _show_patch(self) -> None:
        self.query_one(PullRequestPatch).update(_patch(self._files, self._highlighted_file()))

    def _highlighted_file(self) -> PullRequestFile | None:
        index = self.query_one(PullRequestFiles).highlighted
        if not self._files or index is None or index >= len(self._files):
            return None

        return self._files[index]


def _option(a_file: PullRequestFile) -> Text:
    return Text.assemble(
        (a_file.filename, "bold"),
        " ",
        (a_file.status, MUTED),
        " ",
        (f"+{a_file.additions}", OK),
        " ",
        (f"{_MINUS}{a_file.deletions}", ERROR),
    )


def _index(files: list[PullRequestFile], filename: str | None) -> int | None:
    if not files:
        return None

    return next((index for index, a_file in enumerate(files) if a_file.filename == filename), 0)


def _patch(files: list[PullRequestFile] | None, a_file: PullRequestFile | None) -> RenderableType:
    if files is None:
        return Text()

    if a_file is None:
        return Text(_NO_FILES, style=MUTED)

    if a_file.patch is None:
        return Text(_NO_PATCH, style=WARNING)

    return Syntax(a_file.patch, "diff", theme="ansi_dark", background_color="default", word_wrap=True)

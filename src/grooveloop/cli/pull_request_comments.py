from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static

from grooveloop.cli.loops_render import format_age
from grooveloop.cli.palette import FOCUS, MUTED

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.shared.domain.pull_request_comment import PullRequestComment

_NO_COMMENTS = "no comments"
_UNKNOWN_AUTHOR = "unknown"
_SEPARATOR = " · "


class PullRequestCommentHeader(Static):
    pass


class PullRequestCommentHunk(Static):
    pass


class PullRequestCommentBody(Markdown):
    pass


class PullRequestComments(VerticalScroll):
    DEFAULT_CSS = """
    PullRequestComments PullRequestCommentHeader { padding: 1 1 0 1; }
    PullRequestComments PullRequestCommentHunk { padding: 0 1; }
    PullRequestComments PullRequestCommentBody { padding: 0 1; }
    PullRequestComments .-empty { padding: 1 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._comments: list[PullRequestComment] | None = None

    def show(self, comments: list[PullRequestComment] | None, now: datetime) -> None:
        if comments == self._comments:
            for header, comment in zip(self.query(PullRequestCommentHeader), comments or [], strict=False):
                header.update(_header(comment, now))

            return

        self._comments = comments
        self.remove_children()
        self.mount_all(_widgets(comments, now))


def _widgets(comments: list[PullRequestComment] | None, now: datetime) -> list[Static | Markdown]:
    if comments is None:
        return []

    if not comments:
        return [Static(Text(_NO_COMMENTS, style=MUTED), classes="-empty")]

    widgets: list[Static | Markdown] = []
    for comment in comments:
        widgets.append(PullRequestCommentHeader(_header(comment, now)))
        if comment.diff_hunk is not None:
            widgets.append(PullRequestCommentHunk(Text(comment.diff_hunk, style=MUTED)))
        widgets.append(PullRequestCommentBody(comment.body, open_links=False))

    return widgets


def _header(comment: PullRequestComment, now: datetime) -> Text:
    parts = [
        Text(comment.author or _UNKNOWN_AUTHOR, style="bold"),
        Text(format_age(int((now - comment.created_at).total_seconds())), style=MUTED),
    ]
    if comment.path is not None:
        parts.append(Text(comment.path if comment.line is None else f"{comment.path}:{comment.line}", style=FOCUS))

    return Text(_SEPARATOR).join(parts)

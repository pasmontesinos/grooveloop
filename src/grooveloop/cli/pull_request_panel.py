from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual import on
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Markdown, Static, TabbedContent, TabPane, Tabs

from grooveloop.cli.loops_render import format_age
from grooveloop.cli.palette import ERROR, MUTED, OK, WARNING
from grooveloop.cli.pull_request_comments import PullRequestComments
from grooveloop.cli.pull_request_diff import PullRequestDiff
from grooveloop.cli.watch_render import LESSON_LABELS
from grooveloop.shared.domain.pull_request_detail_state import PullRequestDetailState

if TYPE_CHECKING:
    from datetime import datetime

    from textual.app import ComposeResult

    from grooveloop.cli.watch_render import LearningLine, PullRequestLine, SliceLine
    from grooveloop.shared.domain.pull_request_comment import PullRequestComment
    from grooveloop.shared.domain.pull_request_detail_reading import PullRequestDetailReading
    from grooveloop.shared.domain.pull_request_file import PullRequestFile

_PULL_REQUEST_TAB = "PR"
_DIFF_TAB = "Diff"
_DIFF_PANE_ID = "pull-request-diff"
_COMMENTS_TAB = "Comments"
_COMMENTS_PANE_ID = "pull-request-comments"
_NO_PULL_REQUEST = "no PR yet"
_NO_CONVENTIONS_PULL_REQUEST = "no conventions PR yet"
_LESSON = "Lesson"
_SEPARATOR = " · "
_MINUS = "\u2212"
_CHECKS = {
    "success": Text("✓", style=OK),
    "failure": Text("✗", style=ERROR),
    "error": Text("✗", style=ERROR),
    "pending": Text("⏳", style=WARNING),
    "expected": Text("⏳", style=WARNING),
}
_NO_CHECKS = Text("—", style=MUTED)
_MERGEABLE = {
    "mergeable": Text("✓", style=OK),
    "conflicting": Text("✗ conflicts", style=ERROR),
}
_UNKNOWN_MERGEABLE = Text("? pending", style=WARNING)
_WAITING_FOR_DETAIL = Text("waiting for the next tick", style=WARNING)
_UNREADABLE_DETAIL = Text("unreadable detail (unknown version)", style=ERROR)


class PullRequestSummary(Static):
    pass


class PullRequestBody(Markdown):
    pass


class PullRequestPanel(Vertical):
    ALLOW_MAXIMIZE: ClassVar[bool | None] = True
    DEFAULT_CSS = """
    PullRequestPanel { width: 1fr; border: round $border; background: $panel; padding: 0 1; margin: 0 1 0 0; }
    PullRequestPanel.-maximized { width: 1fr; }
    PullRequestPanel PullRequestSummary { padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane(_PULL_REQUEST_TAB), VerticalScroll():
                yield PullRequestSummary()
                yield PullRequestBody(open_links=False)
            with TabPane(_DIFF_TAB, id=_DIFF_PANE_ID):
                yield PullRequestDiff()
            with TabPane(_COMMENTS_TAB, id=_COMMENTS_PANE_ID):
                yield PullRequestComments()

    def on_mount(self) -> None:
        self.query_one(Tabs).can_focus = False

    @on(TabbedContent.TabActivated)
    def _move_focus_to_the_chosen_tab(self, event: TabbedContent.TabActivated) -> None:
        focused = self.screen.focused
        if focused is None or self not in focused.ancestors or event.pane in focused.ancestors:
            return

        self.screen.set_focus(next((widget for widget in event.pane.query("*") if widget.focusable), None))

    def show(self, a_slice: SliceLine | None, reading: PullRequestDetailReading | None, now: datetime) -> None:
        self._show(_title(a_slice), _summary(a_slice), reading, now)

    def show_lesson(self, learning: LearningLine, reading: PullRequestDetailReading | None, now: datetime) -> None:
        self._show(_lesson_title(learning), _lesson_summary(learning), reading, now)

    def _show(self, title: str, summary: Text, reading: PullRequestDetailReading | None, now: datetime) -> None:
        self.border_title = title
        self.query_one(PullRequestSummary).update(_with_sync(summary, reading, now))
        body = self.query_one(PullRequestBody)
        source = _body(reading)
        if body.source != source:
            body.update(source)
        self.query_one(PullRequestDiff).show(_files(reading))
        comments = _comments(reading)
        self.query_one(TabbedContent).get_tab(_COMMENTS_PANE_ID).label = _comments_label(comments)
        self.query_one(PullRequestComments).show(comments, now)


def _title(a_slice: SliceLine | None) -> str:
    if a_slice is None:
        return ""

    if a_slice.pr_number is None:
        return f"Slice {a_slice.order}"

    return f"Slice {a_slice.order}{_SEPARATOR}PR #{a_slice.pr_number}"


def _lesson_title(learning: LearningLine) -> str:
    title = _LESSON if learning.number is None else f"{_LESSON} #{learning.number}"
    if learning.conventions_pr_number is None:
        return title

    return f"{title}{_SEPARATOR}PR #{learning.conventions_pr_number}"


def _lesson_summary(learning: LearningLine) -> Text:
    status = Text(f"lesson {LESSON_LABELS[learning.status]}", style=MUTED)
    if learning.conventions_pr_number is None:
        return Text("\n").join([Text(_NO_CONVENTIONS_PULL_REQUEST, style=MUTED), status])

    return Text("\n").join([Text(f"#{learning.conventions_pr_number} conventions PR", style="bold"), status])


def _summary(a_slice: SliceLine | None) -> Text:
    if a_slice is None:
        return Text()

    if a_slice.pr_number is None:
        return Text(_NO_PULL_REQUEST, style=MUTED)

    if a_slice.pull_request is None:
        return Text(f"#{a_slice.pr_number}", style="bold")

    return _pull_request_summary(a_slice.pr_number, a_slice.pull_request)


def _with_sync(summary: Text, reading: PullRequestDetailReading | None, now: datetime) -> Text:
    if reading is None:
        return summary

    return Text("\n").join([summary, _sync(reading, now)])


def _sync(reading: PullRequestDetailReading, now: datetime) -> Text:
    if reading.detail is not None:
        return Text(f"synced {format_age(int((now - reading.detail.synced_at).total_seconds()))}", style=MUTED)

    if reading.state == PullRequestDetailState.UNREADABLE:
        return _UNREADABLE_DETAIL

    return _WAITING_FOR_DETAIL


def _body(reading: PullRequestDetailReading | None) -> str:
    if reading is None or reading.detail is None:
        return ""

    return reading.detail.body


def _files(reading: PullRequestDetailReading | None) -> list[PullRequestFile] | None:
    if reading is None or reading.detail is None:
        return None

    return reading.detail.files


def _comments(reading: PullRequestDetailReading | None) -> list[PullRequestComment] | None:
    if reading is None or reading.detail is None:
        return None

    return sorted(reading.detail.conversation + reading.detail.review, key=lambda comment: comment.created_at)


def _comments_label(comments: list[PullRequestComment] | None) -> str:
    if comments is None:
        return _COMMENTS_TAB

    return f"{_COMMENTS_TAB} {len(comments)}"


def _pull_request_summary(number: str, pull_request: PullRequestLine) -> Text:
    return Text("\n").join(
        [
            Text(f"#{number} {pull_request.title}", style="bold"),
            Text(_SEPARATOR).join(
                [
                    Text.assemble(
                        (f"+{pull_request.additions}", OK), " ", (f"{_MINUS}{pull_request.deletions}", ERROR)
                    ),
                    Text(f"{pull_request.changed_files} files"),
                    Text.assemble("checks ", _CHECKS.get(pull_request.checks or "", _NO_CHECKS)),
                ]
            ),
            Text(_SEPARATOR).join(
                [
                    Text.assemble("mergeable ", _MERGEABLE.get(pull_request.mergeable, _UNKNOWN_MERGEABLE)),
                    Text(f"updated {format_age(pull_request.age_seconds)}", style=MUTED),
                ]
            ),
        ]
    )

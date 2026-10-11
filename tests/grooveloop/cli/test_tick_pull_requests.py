from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import create_autospec

from grooveloop.cli.tick_pull_requests import PullRequestsSource, TickPullRequests
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.loop_snapshot import LoopSnapshot
from grooveloop.shared.domain.pull_request_comment import PullRequestComment
from grooveloop.shared.domain.pull_request_detail import PullRequestDetail
from grooveloop.shared.domain.pull_request_file import PullRequestFile
from grooveloop.shared.domain.snapshot_lesson import SnapshotLesson
from grooveloop.shared.domain.snapshot_lesson_status import SnapshotLessonStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus
from grooveloop.shared.domain.snapshot_tick import SnapshotTick
from grooveloop.shared.domain.tick_outcome import TickOutcome
from grooveloop.shared.infrastructure.github_pull_request_contents import (
    GithubPullRequestContents,
    PullRequestContents,
)
from grooveloop.shared.infrastructure.github_story_graph import (
    CommentNode,
    GithubStoryGraph,
    IssueNode,
    PullRequestNode,
)
from tests.playground.shared.infrastructure.fake_loop_snapshots import FakeLoopSnapshots
from tests.playground.shared.infrastructure.fake_pull_request_details import FakePullRequestDetails

if TYPE_CHECKING:
    import pytest

_REPO = "acme/sample"
_UPDATED_AT = datetime(2026, 9, 25, 10, tzinfo=UTC)
_SYNCED_AT = datetime(2026, 9, 25, 12, tzinfo=UTC)
_FILE = PullRequestFile(filename="src/x.py", status="modified", additions=3, deletions=1, patch="@@ -1 +1 @@")


def _pull(
    number: int,
    *,
    merged: bool = False,
    closed: bool = False,
    updated_at: datetime = _UPDATED_AT,
    head_ref_oid: str = "abc123",
    conversation: list[CommentNode] | None = None,
    review: list[CommentNode] | None = None,
) -> PullRequestNode:
    return PullRequestNode(
        number=number,
        merged=merged,
        closed=closed,
        last_commit_at=None,
        conversation=conversation or [],
        review=review or [],
        title="Member roles",
        additions=3,
        deletions=1,
        changed_files=1,
        updated_at=updated_at,
        head_ref_oid=head_ref_oid,
        mergeable="MERGEABLE",
        checks="SUCCESS",
    )


def _node(number: int, pull_request: PullRequestNode | None) -> IssueNode:
    return IssueNode(number=number, title="", body="", labels=[], closed=False, pull_request=pull_request)


def _stored(number: int, *, updated_at: datetime = _UPDATED_AT, head_ref_oid: str = "abc123") -> PullRequestDetail:
    return PullRequestDetail(
        number=number,
        body="before",
        updated_at=updated_at,
        head_ref_oid=head_ref_oid,
        checks="success",
        synced_at=_UPDATED_AT,
        files=[],
        conversation=[],
        review=[],
    )


def _graph_returning(*nodes: IssueNode, pull_requests: list[PullRequestNode] | None = None) -> Any:
    graph = create_autospec(GithubStoryGraph, spec_set=True, instance=True)
    graph.nodes.return_value = list(nodes)
    by_number = {pull.number: pull for pull in pull_requests or []}
    graph.pull_request.side_effect = by_number.get

    return graph


def _lesson(conventions_pull_request_number: int | None, *, resolved: bool = False) -> SnapshotLesson:
    return SnapshotLesson(
        number="30",
        source_pull_request_number=12,
        status=SnapshotLessonStatus.LEARNED,
        conventions_pull_request_number=conventions_pull_request_number,
        resolved=resolved,
    )


def _snapshots_with(*lessons: SnapshotLesson) -> FakeLoopSnapshots:
    return FakeLoopSnapshots(
        [
            LoopSnapshot(
                repo=_REPO,
                tick=SnapshotTick(outcome=TickOutcome.OK, at=_UPDATED_AT, duration_seconds=1, interval_seconds=600),
                stories=[
                    SnapshotStory(
                        number="10", status=SnapshotStoryStatus.SLICED, title="", slices=[], lessons=list(lessons)
                    )
                ],
            )
        ]
    )


def _contents() -> Any:
    contents = create_autospec(GithubPullRequestContents, spec_set=True, instance=True)
    contents.read.return_value = PullRequestContents(body="## Summary", files=[_FILE])

    return contents


def _clock() -> Any:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = _SYNCED_AT

    return clock


def _tick_pull_requests(
    details: FakePullRequestDetails, graph: Any, contents: Any, snapshots: FakeLoopSnapshots | None = None
) -> TickPullRequests:
    return TickPullRequests(
        details=details,
        repo=_REPO,
        clock=_clock(),
        snapshots=snapshots or FakeLoopSnapshots(),
        source=PullRequestsSource(graph=graph, contents=contents),
    )


class TestTickPullRequests:
    def test_should_publish_the_detail_of_an_open_pull_request(self) -> None:
        details = FakePullRequestDetails()
        graph = _graph_returning(
            _node(
                11,
                _pull(
                    12,
                    conversation=[CommentNode(body="summary", created_at=_UPDATED_AT, author="reviewer-bot")],
                    review=[
                        CommentNode(
                            body="use the port",
                            created_at=_UPDATED_AT,
                            database_id=555,
                            path="src/x.py",
                            line=10,
                            diff_hunk="@@ @@",
                            author="octocat",
                        )
                    ],
                ),
            )
        )

        _tick_pull_requests(details, graph, _contents()).publish()

        assert details.published == [
            PullRequestDetail(
                number=12,
                body="## Summary",
                updated_at=_UPDATED_AT,
                head_ref_oid="abc123",
                checks="success",
                synced_at=_SYNCED_AT,
                files=[_FILE],
                conversation=[PullRequestComment(author="reviewer-bot", body="summary", created_at=_UPDATED_AT)],
                review=[
                    PullRequestComment(
                        author="octocat",
                        body="use the port",
                        created_at=_UPDATED_AT,
                        path="src/x.py",
                        line=10,
                        diff_hunk="@@ @@",
                    )
                ],
            )
        ]

    def test_should_not_read_a_pull_request_that_did_not_change(self) -> None:
        details = FakePullRequestDetails([_stored(12)])
        contents = _contents()

        _tick_pull_requests(details, _graph_returning(_node(11, _pull(12))), contents).publish()

        contents.read.assert_not_called()
        assert details.published == []

    def test_should_rewrite_only_the_pull_request_whose_head_changed(self) -> None:
        details = FakePullRequestDetails([_stored(12), _stored(13)])
        contents = _contents()
        graph = _graph_returning(_node(11, _pull(12, head_ref_oid="def456")), _node(14, _pull(13)))

        _tick_pull_requests(details, graph, contents).publish()

        contents.read.assert_called_once_with(12)
        assert [detail.head_ref_oid for detail in details.published] == ["def456"]

    def test_should_rewrite_a_pull_request_whose_update_instant_changed(self) -> None:
        details = FakePullRequestDetails([_stored(12)])
        later = datetime(2026, 9, 25, 11, tzinfo=UTC)

        _tick_pull_requests(details, _graph_returning(_node(11, _pull(12, updated_at=later))), _contents()).publish()

        assert [detail.updated_at for detail in details.published] == [later]

    def test_should_remove_the_detail_of_the_pull_requests_no_longer_open(self) -> None:
        details = FakePullRequestDetails([_stored(12), _stored(13), _stored(15)])
        contents = _contents()
        graph = _graph_returning(
            _node(11, _pull(12, merged=True)), _node(14, _pull(13, closed=True)), _node(16, _pull(15)), _node(17, None)
        )

        _tick_pull_requests(details, graph, contents).publish()

        contents.read.assert_not_called()
        assert details.numbers() == [15]

    def test_should_keep_the_previous_detail_and_go_on_when_a_pull_request_fails_to_sync(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        details = FakePullRequestDetails([_stored(12, head_ref_oid="old")])
        contents = _contents()
        contents.read.side_effect = [RuntimeError("502 Bad Gateway"), PullRequestContents(body="", files=[])]
        graph = _graph_returning(_node(11, _pull(12)), _node(14, _pull(13)))

        _tick_pull_requests(details, graph, contents).publish()

        assert details.find(_REPO, 12) == _stored(12, head_ref_oid="old")
        assert [detail.number for detail in details.published] == [13]
        assert "[warn] pull request #12 sync failed in acme/sample: 502 Bad Gateway" in capsys.readouterr().err

    def test_should_keep_every_detail_when_the_graph_cannot_be_read(self, capsys: pytest.CaptureFixture[str]) -> None:
        details = FakePullRequestDetails([_stored(12)])
        graph = create_autospec(GithubStoryGraph, spec_set=True, instance=True)
        graph.nodes.side_effect = RuntimeError("timeout")

        _tick_pull_requests(details, graph, _contents()).publish()

        assert details.numbers() == [12]
        assert "[warn] pull request details read failed in acme/sample: timeout" in capsys.readouterr().err

    def test_should_publish_nothing_without_a_source(self) -> None:
        details = FakePullRequestDetails([_stored(12)])

        TickPullRequests(
            details=details, repo=_REPO, clock=_clock(), snapshots=FakeLoopSnapshots(), source=None
        ).publish()

        assert details.numbers() == [12]


class TestTickPullRequestsOfLessons:
    def test_should_publish_the_detail_of_the_open_conventions_pull_request_of_a_lesson(self) -> None:
        details = FakePullRequestDetails()
        graph = _graph_returning(pull_requests=[_pull(40)])

        _tick_pull_requests(details, graph, _contents(), _snapshots_with(_lesson(40))).publish()

        assert [detail.number for detail in details.published] == [40]
        assert details.numbers() == [40]

    def test_should_not_read_a_conventions_pull_request_that_did_not_change(self) -> None:
        details = FakePullRequestDetails([_stored(40)])
        contents = _contents()
        graph = _graph_returning(pull_requests=[_pull(40)])

        _tick_pull_requests(details, graph, contents, _snapshots_with(_lesson(40))).publish()

        contents.read.assert_not_called()
        assert details.numbers() == [40]

    def test_should_remove_the_detail_of_a_conventions_pull_request_no_longer_open(self) -> None:
        details = FakePullRequestDetails([_stored(40), _stored(41), _stored(42)])
        contents = _contents()
        graph = _graph_returning(pull_requests=[_pull(40, merged=True), _pull(41, closed=True)])
        snapshots = _snapshots_with(_lesson(40), _lesson(41), _lesson(42, resolved=True), _lesson(None))

        _tick_pull_requests(details, graph, contents, snapshots).publish()

        contents.read.assert_not_called()
        assert details.numbers() == []

    def test_should_not_ask_for_the_conventions_pull_request_of_a_resolved_lesson(self) -> None:
        graph = _graph_returning()

        _tick_pull_requests(
            FakePullRequestDetails(), graph, _contents(), _snapshots_with(_lesson(42, resolved=True))
        ).publish()

        graph.pull_request.assert_not_called()

    def test_should_keep_the_previous_detail_and_go_on_when_a_conventions_pull_request_fails_to_read(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        details = FakePullRequestDetails([_stored(40), _stored(12)])
        graph = _graph_returning(_node(11, _pull(12)))
        graph.pull_request.side_effect = [RuntimeError("502 Bad Gateway"), _pull(41)]

        _tick_pull_requests(details, graph, _contents(), _snapshots_with(_lesson(40), _lesson(41))).publish()

        assert details.numbers() == [12, 40, 41]
        assert "[warn] pull request #40 sync failed in acme/sample: 502 Bad Gateway" in capsys.readouterr().err

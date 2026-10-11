from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import create_autospec

from grooveloop.cli.story_snapshot import StorySnapshot
from grooveloop.shared.domain.snapshot_mergeability import SnapshotMergeability
from grooveloop.shared.domain.snapshot_pull_request import SnapshotPullRequest
from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus
from grooveloop.shared.infrastructure.github_story_graph import (
    GithubStoryGraph,
    IssueNode,
    PullRequestNode,
    StoryNodes,
)

_SPEC = "## Slices\n\n### first slice\n\nbody\n"


def _node(
    number: int, *labels: str, title: str = "", body: str = "", pull_request: PullRequestNode | None = None
) -> IssueNode:
    return IssueNode(
        number=number, title=title, body=body, labels=list(labels), closed=False, pull_request=pull_request
    )


def _pull_request(checks: str | None) -> PullRequestNode:
    return PullRequestNode(
        number=12,
        merged=False,
        closed=False,
        last_commit_at=None,
        conversation=[],
        review=[],
        title="Member roles",
        additions=180,
        deletions=22,
        changed_files=7,
        updated_at=datetime(2026, 9, 24, 10, tzinfo=UTC),
        head_ref_oid="abc123",
        mergeable="MERGEABLE",
        checks=checks,
    )


def _graph_returning(*stories: StoryNodes) -> Any:
    graph = create_autospec(GithubStoryGraph, spec_set=True, instance=True)
    graph.stories.return_value = list(stories)

    return graph


class TestStorySnapshot:
    def test_should_map_each_story_with_its_slices(self) -> None:
        graph = _graph_returning(
            StoryNodes(
                story=_node(10, "grooveloop", "sliced", title="panel", body=_SPEC),
                slices=[_node(11, "grooveloop", "story:10", "dispatched", "pr:12", title="first slice")],
            )
        )

        stories = StorySnapshot(graph).read()

        assert stories == [
            SnapshotStory(
                number="10",
                status=SnapshotStoryStatus.SLICED,
                title="panel",
                slices=[
                    SnapshotSlice(
                        number="11", status=SnapshotSliceStatus.DISPATCHED, title="first slice", pr_number="12"
                    )
                ],
                lessons=[],
            )
        ]

    def test_should_publish_the_dependencies_declared_by_the_sub_issue_in_their_order(self) -> None:
        graph = _graph_returning(
            StoryNodes(
                story=_node(10, "grooveloop", body=_SPEC),
                slices=[
                    _node(
                        13,
                        "grooveloop",
                        "story:10",
                        body="body\n\n<!-- grooveloop:depends-on -->\n**Depends on:** #12, #11",
                    )
                ],
            )
        )

        assert StorySnapshot(graph).read()[0].slices[0].depends_on == ["12", "11"]

    def test_should_publish_no_dependencies_when_the_sub_issue_declares_none(self) -> None:
        graph = _graph_returning(
            StoryNodes(
                story=_node(10, "grooveloop", body=_SPEC),
                slices=[_node(11, "grooveloop", "story:10", body="plain body")],
            )
        )

        assert StorySnapshot(graph).read()[0].slices[0].depends_on == []

    def test_should_publish_the_review_summary_of_the_pull_request_of_a_slice(self) -> None:
        graph = _graph_returning(
            StoryNodes(
                story=_node(10, "grooveloop", body=_SPEC),
                slices=[_node(11, "grooveloop", "story:10", "pr:12", pull_request=_pull_request(checks="SUCCESS"))],
            )
        )

        assert StorySnapshot(graph).read()[0].slices[0].pull_request == SnapshotPullRequest(
            title="Member roles",
            additions=180,
            deletions=22,
            changed_files=7,
            updated_at=datetime(2026, 9, 24, 10, tzinfo=UTC),
            head_ref_oid="abc123",
            mergeable=SnapshotMergeability.MERGEABLE,
            checks="success",
        )

    def test_should_publish_the_checks_as_empty_when_the_pull_request_has_none(self) -> None:
        graph = _graph_returning(
            StoryNodes(
                story=_node(10, "grooveloop", body=_SPEC),
                slices=[_node(11, "grooveloop", "story:10", pull_request=_pull_request(checks=None))],
            )
        )

        pull_request = StorySnapshot(graph).read()[0].slices[0].pull_request

        assert pull_request is not None
        assert pull_request.checks is None

    def test_should_publish_no_pull_request_for_a_slice_without_one(self) -> None:
        graph = _graph_returning(
            StoryNodes(
                story=_node(10, "grooveloop", body=_SPEC),
                slices=[_node(11, "grooveloop", "story:10", "pending")],
            )
        )

        assert StorySnapshot(graph).read()[0].slices[0].pull_request is None

    def test_should_skip_stories_without_a_sliced_spec(self) -> None:
        graph = _graph_returning(
            StoryNodes(story=_node(10, "grooveloop", title="no spec", body="plain description"), slices=[])
        )

        assert StorySnapshot(graph).read() == []

    def test_should_default_a_slice_without_a_status_label_to_pending(self) -> None:
        graph = _graph_returning(
            StoryNodes(
                story=_node(10, "grooveloop", body=_SPEC),
                slices=[_node(11, "grooveloop", "story:10", "order:1")],
            )
        )

        assert StorySnapshot(graph).read()[0].slices[0].status == "pending"

    def test_should_leave_the_pull_request_number_empty_without_a_pr_label(self) -> None:
        graph = _graph_returning(
            StoryNodes(
                story=_node(10, "grooveloop", body=_SPEC),
                slices=[_node(11, "grooveloop", "story:10", "pending")],
            )
        )

        assert StorySnapshot(graph).read()[0].slices[0].pr_number is None

    def test_should_read_the_done_status_of_a_story(self) -> None:
        graph = _graph_returning(StoryNodes(story=_node(10, "grooveloop", "sliced", "done", body=_SPEC), slices=[]))

        assert StorySnapshot(graph).read()[0].status == "done"

    def test_should_read_the_ready_status_of_a_story(self) -> None:
        graph = _graph_returning(
            StoryNodes(story=_node(10, "grooveloop", "ready_for_implementation", body=_SPEC), slices=[])
        )

        assert StorySnapshot(graph).read()[0].status == "ready_for_implementation"

    def test_should_mark_a_story_without_lifecycle_labels_as_draft(self) -> None:
        graph = _graph_returning(StoryNodes(story=_node(10, "grooveloop", body=_SPEC), slices=[]))

        assert StorySnapshot(graph).read()[0].status == "draft"

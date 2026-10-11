from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.shared.domain.snapshot_mergeability import SnapshotMergeability
from grooveloop.shared.domain.snapshot_pull_request import SnapshotPullRequest
from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
from grooveloop.shared.domain.snapshot_slice_status import SnapshotSliceStatus
from grooveloop.shared.domain.snapshot_story import SnapshotStory
from grooveloop.shared.domain.snapshot_story_status import SnapshotStoryStatus
from grooveloop.shared.infrastructure.github_story_graph import depends_on_of, label_in, label_suffix
from grooveloop.slicing.domain.story_status import StoryStatus
from grooveloop.slicing.infrastructure.spec_markdown_parser import parse_spec

if TYPE_CHECKING:
    from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph, IssueNode, PullRequestNode

_PR_LABEL_PREFIX = "pr:"
_STATUS_VALUES = {status.value for status in SliceStatus}


class StorySnapshot:
    def __init__(self, graph: GithubStoryGraph) -> None:
        self._graph = graph

    def read(self) -> list[SnapshotStory]:
        return [
            SnapshotStory(
                number=str(entry.story.number),
                status=SnapshotStoryStatus(_story_status_of(entry.story).value),
                title=entry.story.title,
                slices=[_snapshot_slice(node) for node in entry.slices],
                lessons=[],
            )
            for entry in self._graph.stories()
            if parse_spec(entry.story.body).items
        ]


def _snapshot_slice(node: IssueNode) -> SnapshotSlice:
    return SnapshotSlice(
        number=str(node.number),
        status=SnapshotSliceStatus(_slice_status_of(node).value),
        title=node.title,
        pr_number=_pull_request_number_of(node),
        depends_on=depends_on_of(node) or [],
        pull_request=_snapshot_pull_request(node.pull_request),
    )


def _snapshot_pull_request(pull: PullRequestNode | None) -> SnapshotPullRequest | None:
    if pull is None:
        return None

    return SnapshotPullRequest(
        title=pull.title,
        additions=pull.additions,
        deletions=pull.deletions,
        changed_files=pull.changed_files,
        updated_at=pull.updated_at,
        head_ref_oid=pull.head_ref_oid,
        mergeable=SnapshotMergeability(pull.mergeable.lower()),
        checks=None if pull.checks is None else pull.checks.lower(),
    )


def _story_status_of(node: IssueNode) -> StoryStatus:
    if StoryStatus.DONE.value in node.labels:
        return StoryStatus.DONE

    if StoryStatus.SLICED.value in node.labels:
        return StoryStatus.SLICED

    if StoryStatus.READY_FOR_IMPLEMENTATION.value in node.labels:
        return StoryStatus.READY_FOR_IMPLEMENTATION

    return StoryStatus.DRAFT


def _slice_status_of(node: IssueNode) -> SliceStatus:
    status = label_in(node, _STATUS_VALUES)

    return SliceStatus(status) if status is not None else SliceStatus.PENDING


def _pull_request_number_of(node: IssueNode) -> str | None:
    return label_suffix(node, _PR_LABEL_PREFIX)

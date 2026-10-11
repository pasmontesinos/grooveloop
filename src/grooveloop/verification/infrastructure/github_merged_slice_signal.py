from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph
from grooveloop.verification.domain.merged_slice import MergedSlice
from grooveloop.verification.domain.merged_slice_signal import MergedSliceSignal
from grooveloop.verification.domain.pull_request_number import PullRequestNumber
from grooveloop.verification.domain.slice_id import SliceId

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
    from grooveloop.shared.infrastructure.github_story_graph import IssueNode, PullRequestNode

_VERIFY_DEPLOY_LABEL = "verify-deploy"
_REPORT_MARKER = "<!-- grooveloop:verify-deploy -->"


class GithubMergedSliceSignal(MergedSliceSignal):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._graph = GithubStoryGraph(repo, cache)

    def merged_slices(self) -> list[MergedSlice]:
        merged_slices = []

        for node in self._graph.nodes():
            pull = node.pull_request

            if _VERIFY_DEPLOY_LABEL in node.labels and pull is not None and pull.merged:
                merged_slices.append(self._to_merged_slice(node, pull))

        return merged_slices

    def _to_merged_slice(self, node: IssueNode, pull: PullRequestNode) -> MergedSlice:
        return MergedSlice(
            slice_id=SliceId(str(node.number)),
            pull_request_number=PullRequestNumber(pull.number),
            title=node.title,
            description=node.body,
            has_report=any(_REPORT_MARKER in comment.body for comment in pull.conversation),
        )

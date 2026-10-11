from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.domain.pull_request_comment import PullRequestComment
from grooveloop.shared.domain.pull_request_detail import PullRequestDetail

if TYPE_CHECKING:
    from grooveloop.shared.domain.clock import Clock
    from grooveloop.shared.domain.loop_snapshots import LoopSnapshots
    from grooveloop.shared.domain.pull_request_details import PullRequestDetails
    from grooveloop.shared.infrastructure.github_pull_request_contents import GithubPullRequestContents
    from grooveloop.shared.infrastructure.github_story_graph import CommentNode, GithubStoryGraph, PullRequestNode


@dataclass(frozen=True)
class PullRequestsSource:
    graph: GithubStoryGraph
    contents: GithubPullRequestContents


class TickPullRequests:
    def __init__(
        self,
        details: PullRequestDetails,
        repo: str,
        clock: Clock,
        snapshots: LoopSnapshots,
        source: PullRequestsSource | None,
    ) -> None:
        self._details = details
        self._repo = repo
        self._clock = clock
        self._snapshots = snapshots
        self._source = source

    def publish(self) -> None:
        if self._source is None:
            return

        try:
            pulls = _open_pulls_of(self._source.graph)
        except Exception as error:
            print(f"[warn] pull request details read failed in {self._repo}: {error}", file=sys.stderr)

            return

        for pull in pulls:
            self._sync(pull, self._source.contents)

        retained = [pull.number for pull in pulls] + self._sync_lessons(self._source)

        try:
            self._details.retain(self._repo, retained)
        except OSError as error:
            print(f"[warn] pull request details cleanup failed in {self._repo}: {error}", file=sys.stderr)

    def _sync(self, pull: PullRequestNode, contents: GithubPullRequestContents) -> None:
        try:
            if _unchanged(self._details.find(self._repo, pull.number), pull):
                return

            self._details.publish(self._repo, self._detail_of(pull, contents))
        except Exception as error:
            self._warn_sync_failed(pull.number, error)

    def _sync_lessons(self, source: PullRequestsSource) -> list[int]:
        retained: list[int] = []

        for number in self._conventions_pull_request_numbers():
            try:
                pull = source.graph.pull_request(number)
            except Exception as error:
                self._warn_sync_failed(number, error)
                retained.append(number)

                continue

            if pull is not None and not pull.merged and not pull.closed:
                self._sync(pull, source.contents)
                retained.append(number)

        return retained

    def _conventions_pull_request_numbers(self) -> list[int]:
        snapshot = self._snapshots.find(self._repo)
        if snapshot is None:
            return []

        return [
            lesson.conventions_pull_request_number
            for story in snapshot.stories
            for lesson in story.lessons
            if lesson.conventions_pull_request_number is not None and not lesson.resolved
        ]

    def _warn_sync_failed(self, number: int, error: Exception) -> None:
        print(f"[warn] pull request #{number} sync failed in {self._repo}: {error}", file=sys.stderr)

    def _detail_of(self, pull: PullRequestNode, contents: GithubPullRequestContents) -> PullRequestDetail:
        read = contents.read(pull.number)

        return PullRequestDetail(
            number=pull.number,
            body=read.body,
            updated_at=pull.updated_at,
            head_ref_oid=pull.head_ref_oid,
            checks=None if pull.checks is None else pull.checks.lower(),
            synced_at=self._clock.now(),
            files=read.files,
            conversation=[_comment_of(comment) for comment in pull.conversation],
            review=[_comment_of(comment) for comment in pull.review],
        )


def _open_pulls_of(graph: GithubStoryGraph) -> list[PullRequestNode]:
    pulls = {
        node.pull_request.number: node.pull_request
        for node in graph.nodes()
        if node.pull_request is not None and not node.pull_request.merged and not node.pull_request.closed
    }

    return list(pulls.values())


def _unchanged(stored: PullRequestDetail | None, pull: PullRequestNode) -> bool:
    return stored is not None and stored.updated_at == pull.updated_at and stored.head_ref_oid == pull.head_ref_oid


def _comment_of(comment: CommentNode) -> PullRequestComment:
    return PullRequestComment(
        author=comment.author,
        body=comment.body,
        created_at=comment.created_at,
        path=comment.path,
        line=comment.line,
        diff_hunk=comment.diff_hunk,
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.learning.domain.learn_signal import LearnSignal
from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.shared.domain.comment_directive import CommentDirective, parse_comment_directives
from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph, story_number_of

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
    from grooveloop.shared.infrastructure.github_story_graph import PullRequestNode

_CAPTURED_REACTION = "ROCKET"


@dataclass(frozen=True)
class _Source:
    pull: PullRequestNode
    story_id: StoryId


class GithubLearnSignal(LearnSignal):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._graph = GithubStoryGraph(repo, cache)

    def merged_pull_requests(self) -> list[SourcePullRequest]:
        return [SourcePullRequest(number) for number in self._sources()]

    def story_of(self, source_pull_request: SourcePullRequest) -> StoryId:
        return self._sources()[source_pull_request.value].story_id

    def comments_of(self, source_pull_request: SourcePullRequest) -> list[LessonComment]:
        source = self._sources().get(source_pull_request.value)
        if source is None:
            return []

        return self._learn_comments_of(source.pull)

    def _sources(self) -> dict[int, _Source]:
        sources: dict[int, _Source] = {}

        for node in self._graph.nodes():
            pull = node.pull_request
            story_number = story_number_of(node)

            if pull is not None and pull.merged and story_number is not None:
                sources.setdefault(pull.number, _Source(pull=pull, story_id=StoryId(story_number)))

        return sources

    def _learn_comments_of(self, pull: PullRequestNode) -> list[LessonComment]:
        inline = [
            LessonComment(
                body=comment.body,
                path=comment.path or "",
                line=comment.line or 0,
                diff_hunk=comment.diff_hunk or "",
                id=comment.node_id,
                captured=_CAPTURED_REACTION in comment.viewer_reactions,
            )
            for comment in pull.review
            if _requests_learning(comment.body)
        ]
        conversation = [
            LessonComment(
                body=comment.body,
                path="",
                line=0,
                diff_hunk="",
                id=comment.node_id,
                captured=_CAPTURED_REACTION in comment.viewer_reactions,
            )
            for comment in pull.conversation
            if _requests_learning(comment.body)
        ]

        return inline + conversation


def _requests_learning(body: str) -> bool:
    return CommentDirective.LEARN in parse_comment_directives(body)

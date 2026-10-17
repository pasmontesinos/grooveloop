from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.learning.domain.lesson_comment_marker import LessonCommentMarker
from grooveloop.shared.infrastructure.github_graphql import GithubGraphQL
from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.learning.domain.lesson_comment import LessonComment
    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache

_CAPTURED_REACTION = "ROCKET"
_ADD_REACTION_MUTATION = (
    "mutation($subject: ID!, $content: ReactionContent!) {"
    " addReaction(input: {subjectId: $subject, content: $content}) { reaction { content } } }"
)


class GithubLessonCommentMarker(LessonCommentMarker):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._graphql = GithubGraphQL(repo.requester)
        self._graph = GithubStoryGraph(repo, cache)

    def mark_captured(self, comments: list[LessonComment]) -> None:
        for comment in comments:
            if comment.id is None:
                continue

            self._graphql.query(_ADD_REACTION_MUTATION, {"subject": comment.id, "content": _CAPTURED_REACTION})

        self._graph.forget()

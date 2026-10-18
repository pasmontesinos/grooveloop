from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.directive_marker import DirectiveMarker
from grooveloop.delivery.infrastructure.github_directive_reactions import REACTION_OF_MARK, taken_at_key
from grooveloop.shared.infrastructure.github_graphql import GithubGraphQL

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.delivery.domain.directive_mark import DirectiveMark
    from grooveloop.delivery.domain.review_comment import ReviewComment
    from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache

_ADD_REACTION_MUTATION = (
    "mutation($subject: ID!, $content: ReactionContent!) {"
    " addReaction(input: {subjectId: $subject, content: $content}) { reaction { content } } }"
)
_REMOVE_REACTION_MUTATION = (
    "mutation($subject: ID!, $content: ReactionContent!) {"
    " removeReaction(input: {subjectId: $subject, content: $content}) { reaction { content } } }"
)


class GithubDirectiveMarker(DirectiveMarker):
    def __init__(self, repo: Repository, cache: GithubReadCache) -> None:
        self._graphql = GithubGraphQL(repo.requester)
        self._cache = cache

    def mark(self, directives: list[ReviewComment], mark: DirectiveMark) -> None:
        for directive in directives:
            if directive.id is None:
                continue

            variables = {"subject": directive.id, "content": REACTION_OF_MARK[mark]}
            if mark in directive.marks:
                self._graphql.query(_REMOVE_REACTION_MUTATION, variables)

            self._graphql.query(_ADD_REACTION_MUTATION, variables)
            self._cache.invalidate(taken_at_key(directive.id))

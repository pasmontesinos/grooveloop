from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.directive_marker import DirectiveMarker
from grooveloop.delivery.infrastructure.github_directive_reactions import REACTION_OF_MARK
from grooveloop.shared.infrastructure.github_graphql import GithubGraphQL

if TYPE_CHECKING:
    from github.Repository import Repository

    from grooveloop.delivery.domain.directive_mark import DirectiveMark
    from grooveloop.delivery.domain.review_comment import ReviewComment

_ADD_REACTION_MUTATION = (
    "mutation($subject: ID!, $content: ReactionContent!) {"
    " addReaction(input: {subjectId: $subject, content: $content}) { reaction { content } } }"
)


class GithubDirectiveMarker(DirectiveMarker):
    def __init__(self, repo: Repository) -> None:
        self._graphql = GithubGraphQL(repo.requester)

    def mark(self, directives: list[ReviewComment], mark: DirectiveMark) -> None:
        for directive in directives:
            if directive.id is None:
                continue

            self._graphql.query(_ADD_REACTION_MUTATION, {"subject": directive.id, "content": REACTION_OF_MARK[mark]})

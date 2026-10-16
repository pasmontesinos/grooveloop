from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Repository import Repository

from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.infrastructure.github_directive_marker import GithubDirectiveMarker
from grooveloop.shared.domain.comment_directive import CommentDirective


def _directive(node_id: str | None) -> ReviewComment:
    return ReviewComment(
        body="/grooveloop-implement: rename the variable",
        created_at=datetime(2026, 6, 2, tzinfo=UTC),
        directives=frozenset({CommentDirective.IMPLEMENT}),
        id=node_id,
    )


@pytest.fixture
def repo() -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.requester.graphql_query.return_value = ({}, {"data": {"addReaction": {"reaction": {"content": "EYES"}}}})

    return repo


@pytest.mark.integration
class TestGithubDirectiveMarker:
    @pytest.mark.parametrize(("mark", "reaction"), [(DirectiveMark.TAKEN, "EYES"), (DirectiveMark.ADDRESSED, "ROCKET")])
    def test_adds_the_reaction_of_the_mark_to_each_directive(
        self, repo: Mock, mark: DirectiveMark, reaction: str
    ) -> None:
        GithubDirectiveMarker(repo).mark([_directive("IC_1"), _directive("PRRC_2")], mark)

        calls = repo.requester.graphql_query.call_args_list
        assert all("addReaction" in call.args[0] for call in calls)
        assert [call.args[1] for call in calls] == [
            {"subject": "IC_1", "content": reaction},
            {"subject": "PRRC_2", "content": reaction},
        ]

    def test_skips_a_directive_without_an_id(self, repo: Mock) -> None:
        GithubDirectiveMarker(repo).mark([_directive(None)], DirectiveMark.TAKEN)

        repo.requester.graphql_query.assert_not_called()

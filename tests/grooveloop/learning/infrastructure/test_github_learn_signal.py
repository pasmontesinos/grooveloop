from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Repository import Repository

from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.domain.story_id import StoryId
from grooveloop.learning.infrastructure.github_learn_signal import GithubLearnSignal
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from tests.playground.shared.infrastructure.github_slice_graph import (
    conversation_comment,
    inline_comment,
    pr_node,
    slice_node,
    wire_story_graph,
)

if TYPE_CHECKING:
    from grooveloop.learning.domain.lesson_comment import LessonComment


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 8, 26, tzinfo=UTC)

    return GithubReadCache(clock)


def _story() -> dict[str, Any]:
    return slice_node(10, "grooveloop", "sliced", body="## Slices\n### First\n")


def _slice_with(number: int, pull: dict[str, Any]) -> dict[str, Any]:
    return slice_node(number, "grooveloop", "story:10", "order:1", state="CLOSED", pull_request=pull)


def _captured(signal: GithubLearnSignal) -> list[tuple[int, list[LessonComment]]]:
    return [
        (pull.value, signal.comments_of(pull)) for pull in signal.merged_pull_requests() if signal.comments_of(pull)
    ]


@pytest.fixture
def repo() -> Any:
    return create_autospec(Repository, spec_set=True, instance=True)


@pytest.mark.integration
class TestGithubLearnSignal:
    def test_captures_every_learn_comment_of_a_merged_loop_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            _story(),
            _slice_with(
                11,
                pr_node(
                    42,
                    state="CLOSED",
                    merged=True,
                    inline=[inline_comment("/grooveloop-learn: inject through the constructor")],
                    conversation=[conversation_comment("/grooveloop-learn: name the fake FakeThing")],
                ),
            ),
        )
        signal = GithubLearnSignal(repo, _cache())

        captured = _captured(signal)

        assert len(captured) == 1
        assert captured[0][0] == 42
        bodies = [comment.body for comment in captured[0][1]]
        assert "inject through the constructor" in bodies[0]
        assert "name the fake FakeThing" in bodies[1]

    def test_captures_a_learn_comment_that_shares_the_body_with_another_directive(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            _story(),
            _slice_with(
                11,
                pr_node(
                    42,
                    state="CLOSED",
                    merged=True,
                    inline=[
                        inline_comment(
                            "/grooveloop-implement: rename the variable\n\n"
                            "/grooveloop-learn: inject through the constructor"
                        )
                    ],
                    conversation=[
                        conversation_comment(
                            "/grooveloop-implement: apply what was said\n\n/grooveloop-learn: name the fake"
                        )
                    ],
                ),
            ),
        )
        signal = GithubLearnSignal(repo, _cache())

        captured = _captured(signal)

        assert len(captured) == 1
        bodies = [comment.body for comment in captured[0][1]]
        assert "inject through the constructor" in bodies[0]
        assert "name the fake" in bodies[1]

    def test_keeps_the_location_of_an_inline_learn_comment(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            _story(),
            _slice_with(
                11,
                pr_node(
                    42,
                    state="CLOSED",
                    merged=True,
                    inline=[
                        inline_comment("/grooveloop-learn: x", path="src/a.py", line=7, diff_hunk="@@ -1,2 +1,3 @@")
                    ],
                ),
            ),
        )
        signal = GithubLearnSignal(repo, _cache())

        comment = _captured(signal)[0][1][0]

        assert comment.path == "src/a.py"
        assert comment.line == 7
        assert comment.diff_hunk == "@@ -1,2 +1,3 @@"

    def test_resolves_the_story_of_the_sub_issue_the_pull_request_closes(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            _story(),
            _slice_with(11, pr_node(42, state="CLOSED", merged=True, inline=[inline_comment("/grooveloop-learn: x")])),
        )
        signal = GithubLearnSignal(repo, _cache())

        assert signal.story_of(SourcePullRequest(42)) == StoryId("10")

    def test_ignores_a_merged_pull_request_of_an_issue_without_story(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(
                11,
                "grooveloop",
                pull_request=pr_node(42, state="CLOSED", merged=True, inline=[inline_comment("/grooveloop-learn: x")]),
            ),
        )
        signal = GithubLearnSignal(repo, _cache())

        assert signal.merged_pull_requests() == []

    def test_reads_the_consolidated_graph_without_any_rest_call(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            _story(),
            _slice_with(11, pr_node(42, state="CLOSED", merged=True, inline=[inline_comment("/grooveloop-learn: x")])),
        )
        signal = GithubLearnSignal(repo, _cache())

        _captured(signal)

        assert repo.requester.graphql_query.call_count == 2
        repo.get_pull.assert_not_called()
        repo.get_issues.assert_not_called()

    def test_captures_a_pull_request_referenced_by_several_issues_only_once(self, repo: Mock) -> None:
        pull = pr_node(42, state="CLOSED", merged=True, inline=[inline_comment("/grooveloop-learn: x")])
        wire_story_graph(repo, _story(), _slice_with(11, pull), _slice_with(12, pull))
        signal = GithubLearnSignal(repo, _cache())

        assert [number for number, _ in _captured(signal)] == [42]

    def test_ignores_a_not_merged_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            _story(),
            _slice_with(11, pr_node(42, merged=False, inline=[inline_comment("/grooveloop-learn: x")])),
        )
        signal = GithubLearnSignal(repo, _cache())

        assert _captured(signal) == []

    def test_ignores_a_merged_pull_request_without_learn_comments(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            _story(),
            _slice_with(
                11,
                pr_node(42, state="CLOSED", merged=True, inline=[inline_comment("/grooveloop-implement: rename")]),
            ),
        )
        signal = GithubLearnSignal(repo, _cache())

        assert _captured(signal) == []

    def test_ignores_an_issue_without_a_linked_pull_request(self, repo: Mock) -> None:
        wire_story_graph(repo, _story(), slice_node(11, "grooveloop", "story:10", state="CLOSED"))
        signal = GithubLearnSignal(repo, _cache())

        assert _captured(signal) == []

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Repository import Repository

from grooveloop.learning.domain.lesson_comment import LessonComment
from grooveloop.learning.domain.source_pull_request import SourcePullRequest
from grooveloop.learning.infrastructure.github_learn_signal import GithubLearnSignal
from grooveloop.learning.infrastructure.github_lesson_comment_marker import GithubLessonCommentMarker
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from tests.playground.shared.infrastructure.github_slice_graph import (
    conversation_comment,
    inline_comment,
    pr_node,
    reactions_added,
    slice_node,
    wire_story_graph,
)


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 8, 26, tzinfo=UTC)

    return GithubReadCache(clock)


def _learn_comment(node_id: str | None) -> LessonComment:
    return LessonComment(
        body="/grooveloop-learn: x",
        path="",
        line=0,
        diff_hunk="",
        id=node_id,
        written_at=datetime(2026, 6, 2, tzinfo=UTC),
    )


def _wire_merged_pull_with_learn_comments(repo: Mock) -> None:
    wire_story_graph(
        repo,
        slice_node(10, "grooveloop", "sliced", body="## Slices\n### First\n"),
        slice_node(
            11,
            "grooveloop",
            "story:10",
            "order:1",
            state="CLOSED",
            pull_request=pr_node(
                42,
                state="CLOSED",
                merged=True,
                inline=[inline_comment("/grooveloop-learn: a", node_id="RC_1")],
                conversation=[conversation_comment("/grooveloop-learn: b", node_id="IC_1")],
            ),
        ),
    )


@pytest.fixture
def repo() -> Any:
    return create_autospec(Repository, spec_set=True, instance=True)


@pytest.mark.integration
class TestGithubLessonCommentMarker:
    def test_adds_the_rocket_of_the_loop_to_each_learn_comment(self, repo: Mock) -> None:
        _wire_merged_pull_with_learn_comments(repo)

        GithubLessonCommentMarker(repo, _cache()).mark_captured([_learn_comment("RC_1"), _learn_comment("IC_1")])

        assert reactions_added(repo) == [("RC_1", "ROCKET"), ("IC_1", "ROCKET")]

    def test_skips_a_learn_comment_without_an_id(self, repo: Mock) -> None:
        _wire_merged_pull_with_learn_comments(repo)

        GithubLessonCommentMarker(repo, _cache()).mark_captured([_learn_comment(None)])

        assert reactions_added(repo) == []

    def test_the_next_read_of_the_learn_signal_sees_the_comments_captured(self, repo: Mock) -> None:
        _wire_merged_pull_with_learn_comments(repo)
        cache = _cache()
        signal = GithubLearnSignal(repo, cache)
        signal.comments_of(SourcePullRequest(42))

        GithubLessonCommentMarker(repo, cache).mark_captured([_learn_comment("RC_1"), _learn_comment("IC_1")])

        assert [comment.captured for comment in signal.comments_of(SourcePullRequest(42))] == [True, True]

    def test_keeps_the_cached_reads_the_reactions_do_not_change(self, repo: Mock) -> None:
        _wire_merged_pull_with_learn_comments(repo)
        cache = _cache()
        cache.get_or_load("pull:42", lambda: "cached", 60)

        GithubLessonCommentMarker(repo, cache).mark_captured([_learn_comment("RC_1")])

        assert cache.get_or_load("pull:42", lambda: "reloaded", 60) == "cached"

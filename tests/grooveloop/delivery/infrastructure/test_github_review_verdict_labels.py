from __future__ import annotations

import pytest

from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.infrastructure.github_review_verdict_labels import review_verdict_of
from grooveloop.shared.infrastructure.github_story_graph import to_issue_node
from tests.playground.shared.infrastructure.github_slice_graph import slice_node


@pytest.mark.integration
class TestReviewVerdictOf:
    def test_reads_the_verdict_from_its_label(self) -> None:
        node = to_issue_node(slice_node(11, "story:10", "under_review", "review:blocking"))

        assert review_verdict_of(node) == ReviewVerdict.BLOCKING

    def test_reads_an_empty_verdict_without_a_review_label(self) -> None:
        node = to_issue_node(slice_node(11, "story:10", "under_review"))

        assert review_verdict_of(node) == ReviewVerdict.EMPTY

    def test_ignores_a_review_label_outside_the_verdict_catalogue(self) -> None:
        node = to_issue_node(slice_node(11, "story:10", "under_review", "review:whatever"))

        assert review_verdict_of(node) == ReviewVerdict.EMPTY

    def test_the_most_blocking_verdict_wins_when_the_agent_leaves_two_labels(self) -> None:
        node = to_issue_node(slice_node(11, "story:10", "under_review", "review:minor", "review:blocked"))

        assert review_verdict_of(node) == ReviewVerdict.BLOCKED

    def test_the_most_blocking_verdict_wins_regardless_of_label_order(self) -> None:
        node = to_issue_node(slice_node(11, "story:10", "under_review", "review:blocking", "review:approve"))

        assert review_verdict_of(node) == ReviewVerdict.BLOCKING

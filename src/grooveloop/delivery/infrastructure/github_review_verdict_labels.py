from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.delivery.domain.review_verdict import ReviewVerdict

if TYPE_CHECKING:
    from grooveloop.shared.infrastructure.github_story_graph import IssueNode

REVIEW_LABEL_PREFIX = "review:"

_BY_PRECEDENCE = [
    ReviewVerdict.BLOCKED,
    ReviewVerdict.BLOCKING,
    ReviewVerdict.MINOR,
    ReviewVerdict.APPROVE,
]
VERDICT_LABELS = [f"{REVIEW_LABEL_PREFIX}{verdict.value}" for verdict in reversed(_BY_PRECEDENCE)]


def review_verdict_of(node: IssueNode) -> ReviewVerdict:
    suffixes = {name.removeprefix(REVIEW_LABEL_PREFIX) for name in node.labels if name.startswith(REVIEW_LABEL_PREFIX)}

    for verdict in _BY_PRECEDENCE:
        if verdict.value in suffixes:
            return verdict

    return ReviewVerdict.EMPTY

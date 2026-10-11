from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.shared.infrastructure.github_story_graph import label_suffix

if TYPE_CHECKING:
    from grooveloop.shared.infrastructure.github_story_graph import IssueNode

REVIEW_ROUND_LABEL_PREFIX = "review-round:"


def review_rounds_of(node: IssueNode) -> int:
    rounds = label_suffix(node, REVIEW_ROUND_LABEL_PREFIX)

    return int(rounds) if rounds is not None else 0

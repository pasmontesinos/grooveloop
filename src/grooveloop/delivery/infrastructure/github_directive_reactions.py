from __future__ import annotations

from datetime import datetime
from typing import Any

from grooveloop.delivery.domain.directive_mark import DirectiveMark

REACTION_OF_MARK = {DirectiveMark.TAKEN: "EYES", DirectiveMark.ADDRESSED: "ROCKET"}

_REACTIONS_LIMIT = 100
_TAKEN_AT_KEY_PREFIX = "reactions:taken-at:"

TAKEN_AT_QUERY = (
    "query($id: ID!) { node(id: $id) { ... on Reactable {"
    f" reactions(content: {REACTION_OF_MARK[DirectiveMark.TAKEN]}, last: {_REACTIONS_LIMIT})"
    " { nodes { createdAt user { isViewer } } } } } }"
)


def taken_at_key(comment_id: str) -> str:
    return f"{_TAKEN_AT_KEY_PREFIX}{comment_id}"


def marks_of(reactions: frozenset[str]) -> frozenset[DirectiveMark]:
    return frozenset(mark for mark, reaction in REACTION_OF_MARK.items() if reaction in reactions)


def taken_at_of(data: dict[str, Any]) -> datetime | None:
    reactions = data["node"]["reactions"]["nodes"]

    return max(
        (
            datetime.fromisoformat(reaction["createdAt"])
            for reaction in reactions
            if reaction["user"] is not None and reaction["user"]["isViewer"]
        ),
        default=None,
    )

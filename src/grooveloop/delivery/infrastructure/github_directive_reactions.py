from __future__ import annotations

from grooveloop.delivery.domain.directive_mark import DirectiveMark

REACTION_OF_MARK = {DirectiveMark.TAKEN: "EYES", DirectiveMark.ADDRESSED: "ROCKET"}


def marks_of(reactions: frozenset[str]) -> frozenset[DirectiveMark]:
    return frozenset(mark for mark, reaction in REACTION_OF_MARK.items() if reaction in reactions)

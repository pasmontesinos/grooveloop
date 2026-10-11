from __future__ import annotations

import re
from enum import StrEnum

_DIRECTIVE_PATTERN = re.compile(r"^[ \t]*/grooveloop-([a-z]+)", re.MULTILINE)


class CommentDirective(StrEnum):
    IMPLEMENT = "implement"
    LEARN = "learn"


_DIRECTIVES_BY_VERB = {member.value: member for member in CommentDirective}


def parse_comment_directives(body: str) -> frozenset[CommentDirective]:
    verbs = _DIRECTIVE_PATTERN.findall(body)

    return frozenset(_DIRECTIVES_BY_VERB[verb] for verb in verbs if verb in _DIRECTIVES_BY_VERB)

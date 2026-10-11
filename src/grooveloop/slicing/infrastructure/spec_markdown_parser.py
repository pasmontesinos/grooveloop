from __future__ import annotations

import re

from grooveloop.slicing.domain.slice_spec_item import SliceSpecItem
from grooveloop.slicing.domain.spec import Spec

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_DEPENDS_ON_BULLET = re.compile(r"^\s*-\s*\*\*Depends on:\*\*\s*(.*)$", re.MULTILINE)
_DEPENDS_ON_POSITIONS = re.compile(r"slices?\s+(\d+(?:\s*,\s*\d+)*)", re.IGNORECASE)
_NO_DEPENDENCY = re.compile(r"\bnone\b", re.IGNORECASE)


def parse_spec(body: str) -> Spec:
    items: list[SliceSpecItem] = []
    in_slices_section = False
    title: str | None = None
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal title, body_lines
        if title is not None:
            order = len(items) + 1
            slice_body = "\n".join(body_lines).strip()
            items.append(
                SliceSpecItem(
                    title=title,
                    order=order,
                    body=slice_body,
                    depends_on=_parse_depends_on(slice_body, order),
                )
            )
        title = None
        body_lines = []

    for line in body.splitlines():
        heading = _HEADING.match(line)

        if heading is not None and len(heading.group(1)) <= 2:
            flush()
            in_slices_section = heading.group(2).strip().lower() == "slices"
        elif heading is not None and len(heading.group(1)) == 3 and in_slices_section:
            flush()
            title = heading.group(2).strip()
        elif in_slices_section and title is not None:
            body_lines.append(line)

    flush()

    return Spec(items=items, text=body)


def _parse_depends_on(body: str, order: int) -> list[int] | None:
    bullet_match = _DEPENDS_ON_BULLET.search(body)

    if bullet_match is None:
        return None

    declaration = bullet_match.group(1)
    positions_match = _DEPENDS_ON_POSITIONS.search(declaration)

    if positions_match is not None:
        positions = [int(position) for position in re.findall(r"\d+", positions_match.group(1))]
        backwards = list(dict.fromkeys(position for position in positions if 1 <= position < order))

        if backwards:
            return backwards

    return [] if _NO_DEPENDENCY.search(declaration) else None

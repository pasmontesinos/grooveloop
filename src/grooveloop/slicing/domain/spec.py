from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.slicing.domain.slice_spec_item import SliceSpecItem


@dataclass(frozen=True)
class Spec:
    items: list[SliceSpecItem]
    text: str = ""

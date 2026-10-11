from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.shared.domain.event import Event

if TYPE_CHECKING:
    from grooveloop.slicing.domain.story_id import StoryId


@dataclass(frozen=True)
class StoryReadyToSlice(Event):
    story_id: StoryId


@dataclass(frozen=True)
class StoryCompleted(Event):
    story_id: StoryId

from __future__ import annotations

from dataclasses import dataclass

from grooveloop.shared.domain.identifier import Identifier


@dataclass(frozen=True)
class StoryId(Identifier): ...

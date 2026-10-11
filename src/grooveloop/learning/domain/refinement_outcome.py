from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.learning.domain.conventions_pull_request import ConventionsPullRequest


@dataclass(frozen=True)
class RefinementOutcome:
    conventions_pull_request: ConventionsPullRequest | None
    discarded: bool

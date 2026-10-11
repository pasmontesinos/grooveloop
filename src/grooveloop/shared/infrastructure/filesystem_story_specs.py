from __future__ import annotations

import os
from typing import TYPE_CHECKING

from grooveloop.shared.domain.story_spec_reading import StorySpecReading
from grooveloop.shared.domain.story_specs import StorySpecs

if TYPE_CHECKING:
    from pathlib import Path

_STORIES_DIR = "stories"
_SPEC_FILE = "spec.md"
_PENDING_FILE = "spec.md.tmp"
_FINAL_NEWLINE = "\n"


class FilesystemStorySpecs(StorySpecs):
    def __init__(self, repos_dir: Path) -> None:
        self._repos_dir = repos_dir

    def publish(self, repo: str, number: int, spec: str) -> None:
        story_dir = self._story_dir(repo, number)
        story_dir.mkdir(parents=True, exist_ok=True)

        pending = story_dir / _PENDING_FILE
        pending.write_bytes(f"{spec}{_FINAL_NEWLINE}".encode())
        os.replace(pending, story_dir / _SPEC_FILE)

    def find(self, repo: str, number: int) -> str | None:
        try:
            stored = (self._story_dir(repo, number) / _SPEC_FILE).read_bytes().decode()
        except (OSError, UnicodeDecodeError):
            return None

        return stored.removesuffix(_FINAL_NEWLINE)

    def read(self, repo: str, number: int) -> StorySpecReading | None:
        try:
            mtime_ns = (self._story_dir(repo, number) / _SPEC_FILE).stat().st_mtime_ns
        except OSError:
            return None

        spec = self.find(repo, number)

        return StorySpecReading(spec=spec, mtime_ns=mtime_ns) if spec is not None else None

    def _story_dir(self, repo: str, number: int) -> Path:
        return self._repos_dir / repo / _STORIES_DIR / str(number)

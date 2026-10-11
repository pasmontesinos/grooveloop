from __future__ import annotations

from grooveloop.shared.domain.story_spec_reading import StorySpecReading
from grooveloop.shared.domain.story_specs import StorySpecs


class FakeStorySpecs(StorySpecs):
    def __init__(self, specs: dict[int, str] | None = None, failing: list[int] | None = None) -> None:
        self.published: list[int] = []
        self._specs = dict(specs or {})
        self._mtimes = dict.fromkeys(self._specs, 0)
        self._failing = failing or []

    def publish(self, repo: str, number: int, spec: str) -> None:
        if number in self._failing:
            raise OSError("read-only file system")

        self.published.append(number)
        self._specs[number] = spec
        self._mtimes[number] = self._mtimes.get(number, 0) + 1

    def find(self, repo: str, number: int) -> str | None:
        return self._specs.get(number)

    def read(self, repo: str, number: int) -> StorySpecReading | None:
        spec = self._specs.get(number)

        return StorySpecReading(spec=spec, mtime_ns=self._mtimes[number]) if spec is not None else None

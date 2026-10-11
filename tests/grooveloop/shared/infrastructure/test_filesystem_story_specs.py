from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.domain.story_spec_reading import StorySpecReading
from grooveloop.shared.infrastructure.filesystem_story_specs import FilesystemStorySpecs

if TYPE_CHECKING:
    from pathlib import Path

_REPO = "acme/tooling"
_BODY = "## Slices\r\n\r\n### First\n\nThe Spec carries accents: ñ.\n\n"


def _story_dir(tmp_path: Path) -> Path:
    return tmp_path / "acme" / "tooling" / "stories" / "464"


@pytest.mark.integration
class TestFilesystemStorySpecs:
    def test_should_write_the_body_of_the_story_followed_by_a_final_newline(self, tmp_path: Path) -> None:
        FilesystemStorySpecs(repos_dir=tmp_path).publish(_REPO, 464, _BODY)

        assert (_story_dir(tmp_path) / "spec.md").read_bytes() == f"{_BODY}\n".encode()

    def test_should_read_back_the_exact_body_it_wrote(self, tmp_path: Path) -> None:
        specs = FilesystemStorySpecs(repos_dir=tmp_path)
        specs.publish(_REPO, 464, _BODY)

        assert specs.find(_REPO, 464) == _BODY

    def test_should_replace_the_previous_spec(self, tmp_path: Path) -> None:
        specs = FilesystemStorySpecs(repos_dir=tmp_path)
        specs.publish(_REPO, 464, "before")

        specs.publish(_REPO, 464, "after")

        assert specs.find(_REPO, 464) == "after"

    def test_should_leave_no_temporary_file_behind(self, tmp_path: Path) -> None:
        FilesystemStorySpecs(repos_dir=tmp_path).publish(_REPO, 464, _BODY)

        assert [path.name for path in _story_dir(tmp_path).iterdir()] == ["spec.md"]

    def test_should_find_no_spec_when_the_file_is_missing(self, tmp_path: Path) -> None:
        assert FilesystemStorySpecs(repos_dir=tmp_path).find(_REPO, 464) is None

    def test_should_read_the_spec_with_the_mtime_of_its_file(self, tmp_path: Path) -> None:
        specs = FilesystemStorySpecs(repos_dir=tmp_path)
        specs.publish(_REPO, 464, _BODY)

        reading = specs.read(_REPO, 464)

        assert reading == StorySpecReading(spec=_BODY, mtime_ns=(_story_dir(tmp_path) / "spec.md").stat().st_mtime_ns)

    def test_should_read_nothing_when_the_file_is_missing(self, tmp_path: Path) -> None:
        assert FilesystemStorySpecs(repos_dir=tmp_path).read(_REPO, 464) is None

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grooveloop.shared.infrastructure.filesystem_agent_profiles import FilesystemAgentProfiles

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestFilesystemAgentProfiles:
    def test_returns_the_embedded_default_when_there_is_no_override(self, tmp_path: Path) -> None:
        profiles = FilesystemAgentProfiles(workdir=str(tmp_path))

        profile = profiles.find("developer")

        assert profile is not None
        assert profile.engine == "claude"
        assert profile.model == "opus"
        assert "superpowers" in profile.persona

    def test_override_replaces_only_the_declared_fields(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / ".grooveloop" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "developer.md").write_text("---\nmodel: sonnet\n---\n")
        profiles = FilesystemAgentProfiles(workdir=str(tmp_path))

        profile = profiles.find("developer")

        assert profile is not None
        assert profile.model == "sonnet"
        assert profile.engine == "claude"
        assert "superpowers" in profile.persona

    def test_returns_none_for_an_unknown_profile(self, tmp_path: Path) -> None:
        profiles = FilesystemAgentProfiles(workdir=str(tmp_path))

        assert profiles.find("unknown") is None

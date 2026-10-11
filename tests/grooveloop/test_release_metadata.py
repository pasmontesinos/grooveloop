from __future__ import annotations

import json
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _project() -> dict[str, object]:
    project: dict[str, object] = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]

    return project


class TestReleaseMetadata:
    def test_the_plugin_declares_the_version_of_the_package(self) -> None:
        plugin = json.loads((_ROOT / "plugins/grooveloop/.claude-plugin/plugin.json").read_text())

        assert plugin.get("version") == _project()["version"]

    def test_the_package_publishes_the_readme_as_its_description(self) -> None:
        assert _project().get("readme") == "README.md"

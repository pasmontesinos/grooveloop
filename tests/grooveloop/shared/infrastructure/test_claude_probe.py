from __future__ import annotations

from unittest.mock import patch

import pytest

from grooveloop.shared.infrastructure.claude_probe import ClaudeProbe


@pytest.mark.integration
class TestClaudeProbe:
    def test_check_should_pass_when_the_binary_is_available(self) -> None:
        with patch("grooveloop.shared.infrastructure.claude_probe.subprocess.run") as run:
            ClaudeProbe().check()

        run.assert_called_once()

    def test_check_should_raise_when_the_binary_is_missing(self) -> None:
        with patch(
            "grooveloop.shared.infrastructure.claude_probe.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(FileNotFoundError):
                ClaudeProbe().check()

    def test_should_expose_a_name(self) -> None:
        assert ClaudeProbe().name == "claude-cli"

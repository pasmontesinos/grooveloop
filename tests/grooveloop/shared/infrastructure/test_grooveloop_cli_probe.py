from __future__ import annotations

from unittest.mock import patch

import pytest

from grooveloop.shared.infrastructure.grooveloop_cli_probe import GrooveloopCliProbe


@pytest.mark.integration
class TestGrooveloopCliProbe:
    def test_check_should_pass_when_the_binary_is_available(self) -> None:
        with patch("grooveloop.shared.infrastructure.grooveloop_cli_probe.subprocess.run") as run:
            GrooveloopCliProbe().check()

        run.assert_called_once()

    def test_check_should_raise_when_the_binary_is_missing(self) -> None:
        with patch(
            "grooveloop.shared.infrastructure.grooveloop_cli_probe.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(FileNotFoundError):
                GrooveloopCliProbe().check()

    def test_should_expose_a_name(self) -> None:
        assert GrooveloopCliProbe().name == "grooveloop-cli"

from __future__ import annotations

import subprocess

from grooveloop.shared.application.probes.probe import Probe

_VERSION_COMMAND = ("claude", "--version")


class ClaudeProbe(Probe):
    name = "claude-cli"

    def check(self) -> None:
        subprocess.run(_VERSION_COMMAND, capture_output=True, check=True)

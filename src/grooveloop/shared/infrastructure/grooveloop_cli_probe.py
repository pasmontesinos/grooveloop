from __future__ import annotations

import subprocess

from grooveloop.shared.application.probes.probe import Probe

_HELP_COMMAND = ("grooveloop", "--help")


class GrooveloopCliProbe(Probe):
    name = "grooveloop-cli"

    def check(self) -> None:
        subprocess.run(_HELP_COMMAND, capture_output=True, check=True)

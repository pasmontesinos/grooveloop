from __future__ import annotations

import subprocess

from grooveloop.shared.application.probes.probe import Probe

_VERSION_COMMAND = ("opencode", "--version")


class OpencodeProbe(Probe):
    name = "opencode-cli"

    def check(self) -> None:
        subprocess.run(_VERSION_COMMAND, capture_output=True, check=True)

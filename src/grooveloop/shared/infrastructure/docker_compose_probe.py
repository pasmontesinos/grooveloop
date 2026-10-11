from __future__ import annotations

import subprocess

from grooveloop.shared.application.probes.probe import Probe

_VERSION_COMMAND = ("docker", "compose", "version")


class DockerComposeProbe(Probe):
    name = "docker-compose-cli"

    def check(self) -> None:
        try:
            subprocess.run(_VERSION_COMMAND, capture_output=True, check=True)
        except FileNotFoundError:
            return

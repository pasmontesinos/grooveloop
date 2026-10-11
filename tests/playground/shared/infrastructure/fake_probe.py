from __future__ import annotations

from grooveloop.shared.application.probes.probe import Probe


class PassingProbe(Probe):
    name = "passing"

    def check(self) -> None:
        return None


class FailingProbe(Probe):
    name = "failing"

    def check(self) -> None:
        raise RuntimeError("not available")

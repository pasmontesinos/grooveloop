from __future__ import annotations

import os
import subprocess

import pytest

from grooveloop.shared.infrastructure.signal_process_liveness import SignalProcessLiveness


@pytest.mark.integration
class TestSignalProcessLiveness:
    def test_should_report_the_current_process_as_alive(self) -> None:
        assert SignalProcessLiveness().is_alive(os.getpid()) is True

    def test_should_report_a_reaped_process_as_not_alive(self) -> None:
        finished = subprocess.Popen(["true"])
        finished.wait()

        assert SignalProcessLiveness().is_alive(finished.pid) is False

    @pytest.mark.parametrize("pid", [0, -1, -12345])
    def test_should_report_a_non_positive_pid_as_not_alive(self, pid: int) -> None:
        assert SignalProcessLiveness().is_alive(pid) is False

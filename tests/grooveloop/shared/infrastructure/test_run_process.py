from __future__ import annotations

import signal
import subprocess

import pytest

from grooveloop.shared.infrastructure.run_process import stop_run_process_group


@pytest.mark.integration
class TestStopRunProcessGroup:
    def test_should_kill_the_group_that_survives_the_termination_grace(self) -> None:
        with subprocess.Popen(
            ["/bin/sh", "-c", "trap '' TERM; echo ready; sleep 30; true"],
            stdout=subprocess.PIPE,
            start_new_session=True,
        ) as process:
            try:
                assert process.stdout is not None
                process.stdout.readline()

                stop_run_process_group(process.pid, grace_seconds=0.3)

                exit_status = process.wait(timeout=5)
            finally:
                process.kill()

        assert exit_status == -signal.SIGKILL

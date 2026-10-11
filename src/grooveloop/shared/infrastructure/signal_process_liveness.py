from __future__ import annotations

import os

from grooveloop.shared.domain.process_liveness import ProcessLiveness

_PROBE_SIGNAL = 0


class SignalProcessLiveness(ProcessLiveness):
    def is_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False

        try:
            os.kill(pid, _PROBE_SIGNAL)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

        return True

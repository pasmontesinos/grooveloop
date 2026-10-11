from __future__ import annotations

import json

_SESSION_KEY = "session_id"


def parse_session_id(log_head: str) -> str | None:
    for line in log_head.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue

        session_id = event.get(_SESSION_KEY) if isinstance(event, dict) else None
        if isinstance(session_id, str) and len(session_id) > 0:
            return session_id

    return None

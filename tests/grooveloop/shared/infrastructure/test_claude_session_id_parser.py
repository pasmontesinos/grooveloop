from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from grooveloop.shared.infrastructure.claude_session_id_parser import parse_session_id

_noise_lines = st.lists(st.text(alphabet=st.characters(exclude_categories=("Cc", "Zl", "Zp"), exclude_characters="{")))
_session_ids = st.text(min_size=1).filter(lambda text: text.strip() == text)


class TestParseSessionIdProperties:
    @given(log_head=st.text())
    def test_returns_nothing_or_a_non_empty_session_id_for_any_text(self, log_head: str) -> None:
        session_id = parse_session_id(log_head)

        assert session_id is None or len(session_id) > 0

    @given(before=_noise_lines, after=_noise_lines, session_id=_session_ids)
    def test_finds_the_session_id_among_lines_that_are_not_json(
        self, before: list[str], after: list[str], session_id: str
    ) -> None:
        event = json.dumps({"type": "system", "session_id": session_id})

        assert parse_session_id("\n".join([*before, event, *after])) == session_id

    @given(first=_session_ids, second=_session_ids)
    def test_returns_the_first_session_id_of_the_log(self, first: str, second: str) -> None:
        log_head = "\n".join(json.dumps({"session_id": session_id}) for session_id in [first, second])

        assert parse_session_id(log_head) == first

    @given(lines=_noise_lines)
    def test_returns_nothing_when_no_line_is_json(self, lines: list[str]) -> None:
        assert parse_session_id("\n".join(lines)) is None

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from grooveloop.verification.domain.verification_section import VerificationSection

_BODY_WITH_SECTION = """- **Type:** vertical
- **Scope:** the new flag.
- **Observable verification:**

  1. `uv run grooveloop run --repo owner/repo` -> `exit=0`.
  2. `gh issue view 11 --json labels` -> includes `verify-deploy`.
"""

_SINGLE_LINE_CONTENT = st.text(
    st.characters(codec="utf-8", exclude_categories=("Cc", "Cs", "Zl", "Zp")), min_size=1
).filter(lambda content: content.strip() != "")


class TestVerificationSectionParse:
    def test_reads_the_commands_under_the_bullet(self) -> None:
        section = VerificationSection.parse(_BODY_WITH_SECTION)

        assert section is not None
        assert "uv run grooveloop run --repo owner/repo" in section.text
        assert "gh issue view 11 --json labels" in section.text

    def test_dedents_the_block(self) -> None:
        section = VerificationSection.parse(_BODY_WITH_SECTION)

        assert section is not None
        assert section.text.startswith("1. `uv run")

    def test_leaves_out_the_bullets_above(self) -> None:
        section = VerificationSection.parse(_BODY_WITH_SECTION)

        assert section is not None
        assert "Type" not in section.text
        assert "Scope" not in section.text

    def test_stops_at_the_next_root_bullet(self) -> None:
        body = "- **Observable verification:**\n\n  1. `gh pr view 42`.\n\n- **Depends on:** none.\n"

        section = VerificationSection.parse(body)

        assert section is not None
        assert "gh pr view 42" in section.text
        assert "Depends on" not in section.text

    def test_stops_at_the_next_heading(self) -> None:
        body = "## Observable verification\n\nRun `make test`.\n\n## Notes\n\nNothing.\n"

        section = VerificationSection.parse(body)

        assert section is not None
        assert "make test" in section.text
        assert "Notes" not in section.text

    def test_reads_the_heading_in_any_case(self) -> None:
        body = "- **OBSERVABLE Verification:**\n\n  Run `make test`.\n"

        section = VerificationSection.parse(body)

        assert section is not None
        assert "make test" in section.text

    def test_reads_the_content_on_the_heading_line(self) -> None:
        body = "- **Observable verification:** `uv run grooveloop loop --once` -> `exit=0`.\n"

        section = VerificationSection.parse(body)

        assert section is not None
        assert section.text == "`uv run grooveloop loop --once` -> `exit=0`."

    def test_joins_the_heading_line_with_the_block_below(self) -> None:
        body = "- **Observable verification:** run:\n\n  1. `gh pr view 42`.\n"

        section = VerificationSection.parse(body)

        assert section is not None
        assert section.text.startswith("run:")
        assert "gh pr view 42" in section.text

    def test_keeps_a_bold_bullet_inside_the_block(self) -> None:
        body = (
            "## Observable verification\n\n"
            "1. `gh pr view 42`.\n\n"
            "- **Note:** restart the loop.\n"
            "2. `gh issue view 11`.\n"
        )

        section = VerificationSection.parse(body)

        assert section is not None
        assert "gh pr view 42" in section.text
        assert "Note" in section.text
        assert "gh issue view 11" in section.text

    def test_reads_a_bold_heading_without_a_bullet(self) -> None:
        body = (
            "**Observable verification**\n\n"
            "After merging to `master`:\n\n"
            "1. `uv run grooveloop doctor`.\n\n"
            "If it fails: `git revert`.\n"
        )

        section = VerificationSection.parse(body)

        assert section is not None
        assert "uv run grooveloop doctor" in section.text
        assert "git revert" in section.text

    def test_returns_none_when_the_section_is_empty(self) -> None:
        assert VerificationSection.parse("- **Observable verification:**\n\n- **Depends on:** none.\n") is None


class TestVerificationSectionParseProperties:
    @given(st.text())
    def test_returns_none_for_a_body_without_the_heading(self, body: str) -> None:
        assert VerificationSection.parse(body) is None

    @given(_SINGLE_LINE_CONTENT)
    def test_keeps_the_content_under_the_heading(self, content: str) -> None:
        section = VerificationSection.parse(f"- **Observable verification:**\n\n  {content}\n")

        assert section is not None
        assert content.strip() in section.text

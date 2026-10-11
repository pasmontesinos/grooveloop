from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from grooveloop.shared.domain.agent_profile_parser import ParsedAgentProfile, parse_agent_profile


class TestParseAgentProfile:
    def test_should_parse_scalars_lists_and_persona(self) -> None:
        content = (
            "---\n"
            "name: developer\n"
            "engine: claude\n"
            "model: opus\n"
            "skills: [brainstorming, tdd]\n"
            "context_files: []\n"
            "---\n"
            "be autonomous\n"
        )

        parsed = parse_agent_profile(content)

        assert parsed == ParsedAgentProfile(
            name="developer",
            engine="claude",
            model="opus",
            skills=["brainstorming", "tdd"],
            context_files=[],
            persona="be autonomous",
        )

    def test_should_parse_block_lists(self) -> None:
        content = "---\nskills:\n  - a\n  - b\n---\nx\n"

        parsed = parse_agent_profile(content)

        assert parsed is not None
        assert parsed.skills == ["a", "b"]

    def test_absent_keys_are_none(self) -> None:
        parsed = parse_agent_profile("---\nmodel: sonnet\n---\n")

        assert parsed is not None
        assert parsed.model == "sonnet"
        assert parsed.name is None
        assert parsed.skills is None
        assert parsed.persona is None

    def test_missing_frontmatter_returns_none(self) -> None:
        assert parse_agent_profile("just a body without frontmatter") is None

    def test_merged_over_overrides_only_present_fields(self) -> None:
        base = ParsedAgentProfile(
            name="developer", engine="claude", model="opus", skills=["a"], context_files=[], persona="base"
        )
        override = ParsedAgentProfile(
            name=None, engine=None, model="sonnet", skills=None, context_files=None, persona=None
        )

        merged = override.merged_over(base)

        assert merged == ParsedAgentProfile(
            name="developer", engine="claude", model="sonnet", skills=["a"], context_files=[], persona="base"
        )

    _value = st.from_regex(r"[A-Za-z0-9 .\-]{1,20}", fullmatch=True).map(str.strip).filter(lambda v: v != "")

    @given(model=_value)
    def test_scalar_value_round_trips(self, model: str) -> None:
        parsed = parse_agent_profile(f"---\nmodel: {model}\n---\nbody\n")

        assert parsed is not None
        assert parsed.model == model

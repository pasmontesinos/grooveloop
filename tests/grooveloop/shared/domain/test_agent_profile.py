from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from grooveloop.shared.domain.agent_profile import AgentProfile
from grooveloop.shared.domain.agent_profile_parser import ParsedAgentProfile


def _profile(
    persona: str = "be useful", skills: list[str] | None = None, context_files: list[str] | None = None
) -> AgentProfile:
    return AgentProfile(
        name="developer",
        engine="claude",
        model="opus",
        skills=skills or [],
        context_files=context_files or [],
        persona=persona,
    )


class TestAgentProfileRender:
    def test_should_append_the_task_after_the_persona(self) -> None:
        result = _profile(persona="create a plan with superpowers").render("implement the slice")

        assert result.startswith("create a plan with superpowers\n\n")
        assert result.endswith("\n\nimplement the slice")

    def test_should_include_skill_and_context_references_between_persona_and_task(self) -> None:
        result = _profile(persona="PERSONA", skills=["brainstorming"], context_files=["docs/x.md"]).render("TASK")

        assert result.index("PERSONA") < result.index("brainstorming") < result.index("TASK")
        assert result.index("brainstorming") < result.index("docs/x.md") < result.index("TASK")

    def test_should_order_reading_each_context_file_before_starting(self) -> None:
        result = _profile(persona="", context_files=["docs/a.md", "docs/b.md"]).render("TASK")

        assert result.startswith(
            "Before you start, read each of these files with the Read tool:\n- docs/a.md\n- docs/b.md\n\n"
        )

    def test_should_order_loading_each_skill_before_starting(self) -> None:
        result = _profile(persona="", skills=["verify-deploy", "superpowers:test-driven-development"]).render("TASK")

        assert result.startswith(
            "Before you start, load each of these skills with the Skill tool:\n"
            "- verify-deploy\n"
            "- superpowers:test-driven-development\n\n"
        )

    def test_should_put_the_foreground_rule_right_before_the_task(self) -> None:
        result = _profile(persona="PERSONA", skills=["verify-deploy"]).render("TASK")

        assert result.index("verify-deploy") < result.index("wait in the foreground") < result.index("TASK")

    def test_should_render_only_the_foreground_rule_and_the_task_when_persona_is_empty(self) -> None:
        result = _profile(persona="").render("t")

        assert result.startswith("Do not run commands in the background")
        assert result.endswith("even if it takes a while, and continue with its result.\n\nt")

    _text = st.text(min_size=1).filter(lambda value: value.strip() != "")

    @given(persona=_text, task=_text)
    def test_render_always_ends_with_the_task_and_contains_the_persona(self, persona: str, task: str) -> None:
        result = _profile(persona=persona).render(task)

        assert result.endswith(task.strip())
        assert persona.strip() in result


class TestAgentProfileFromParsed:
    def test_should_build_a_complete_profile_defaulting_collections_and_persona(self) -> None:
        parsed = ParsedAgentProfile(
            name="developer", engine="claude", model="opus", skills=None, context_files=None, persona=None
        )

        profile = AgentProfile.from_parsed(parsed)

        assert profile == AgentProfile(
            name="developer", engine="claude", model="opus", skills=[], context_files=[], persona=""
        )

    def test_should_return_none_when_a_required_scalar_is_missing(self) -> None:
        parsed = ParsedAgentProfile(
            name="developer", engine="claude", model=None, skills=[], context_files=[], persona="p"
        )

        assert AgentProfile.from_parsed(parsed) is None

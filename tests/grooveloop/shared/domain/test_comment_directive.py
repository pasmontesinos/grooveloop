from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from grooveloop.shared.domain.comment_directive import CommentDirective, parse_comment_directives


class TestParseCommentDirectives:
    def test_recognizes_the_implement_verb(self) -> None:
        assert parse_comment_directives("/grooveloop-implement: rename the variable") == {CommentDirective.IMPLEMENT}

    def test_recognizes_the_learn_verb(self) -> None:
        assert parse_comment_directives("/grooveloop-learn: inject through the constructor") == {CommentDirective.LEARN}

    def test_recognizes_a_directive_indented_at_the_start_of_a_line(self) -> None:
        assert parse_comment_directives("Reviewed.\n  /grooveloop-implement: rename") == {CommentDirective.IMPLEMENT}

    def test_ignores_a_directive_cited_in_the_middle_of_a_line(self) -> None:
        assert parse_comment_directives("please /grooveloop-implement this") == frozenset()

    def test_ignores_the_directives_the_agent_cites_in_its_summary(self) -> None:
        body = "Addressed the comments of the `/grooveloop-implement`.\n\n- No lessons for `/grooveloop-learn`."

        assert parse_comment_directives(body) == frozenset()

    def test_ignores_a_directive_quoted_from_another_comment(self) -> None:
        assert parse_comment_directives("> /grooveloop-implement: rename the variable\n\nDone.") == frozenset()

    def test_recognizes_every_directive_of_the_same_body(self) -> None:
        body = "/grooveloop-implement: rename the variable\n\n/grooveloop-learn: inject through the constructor"

        assert parse_comment_directives(body) == {CommentDirective.IMPLEMENT, CommentDirective.LEARN}

    def test_ignores_an_unknown_verb_without_hiding_the_valid_ones(self) -> None:
        body = "/grooveloop-review this\n\n/grooveloop-learn: inject through the constructor"

        assert parse_comment_directives(body) == {CommentDirective.LEARN}

    def test_returns_no_directive_without_any_verb(self) -> None:
        assert parse_comment_directives("use the SliceRepository port") == frozenset()

    def test_returns_no_directive_for_an_unknown_verb(self) -> None:
        assert parse_comment_directives("/grooveloop-deploy now") == frozenset()

    def test_returns_no_directive_for_an_empty_body(self) -> None:
        assert parse_comment_directives("") == frozenset()

    _surrounding = st.text(alphabet=st.characters(blacklist_characters="/"), max_size=40)
    _text_on_the_same_line = st.text(alphabet=st.characters(blacklist_characters="/\n"), min_size=1, max_size=40)

    @given(prefix=_surrounding, suffix=_surrounding)
    def test_any_body_with_the_implement_directive_starting_a_line_parses_to_implement(
        self, prefix: str, suffix: str
    ) -> None:
        assert CommentDirective.IMPLEMENT in parse_comment_directives(f"{prefix}\n/grooveloop-implement:{suffix}")

    @given(prefix=_text_on_the_same_line.filter(lambda text: text.strip() != ""), suffix=_surrounding)
    def test_any_directive_after_text_on_its_line_parses_to_no_directive(self, prefix: str, suffix: str) -> None:
        assert parse_comment_directives(f"{prefix}/grooveloop-implement:{suffix}") == frozenset()

    @given(body=st.text(max_size=80).filter(lambda text: "/grooveloop-" not in text))
    def test_any_body_without_a_directive_token_parses_to_no_directive(self, body: str) -> None:
        assert parse_comment_directives(body) == frozenset()

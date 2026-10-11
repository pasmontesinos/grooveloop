from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from grooveloop.slicing.domain.slice_spec_item import SliceSpecItem
from grooveloop.slicing.infrastructure.spec_markdown_parser import parse_spec


class TestSpecMarkdownParser:
    def test_should_read_each_h3_under_the_slices_section_as_a_slice(self) -> None:
        body = (
            "## Goal\nblah\n\n## Slices\n### First slice\n- **Type:** infra\n\n### Second slice\n- **Type:** vertical\n"
        )

        spec = parse_spec(body)

        assert spec.items == [
            SliceSpecItem(title="First slice", order=1, body="- **Type:** infra"),
            SliceSpecItem(title="Second slice", order=2, body="- **Type:** vertical"),
        ]

    def test_should_stop_at_the_next_h2_section(self) -> None:
        body = "## Slices\n### Only slice\n\n## Recommended sequence\n### Not a slice\n"

        spec = parse_spec(body)

        assert spec.items == [SliceSpecItem(title="Only slice", order=1)]

    def test_should_not_treat_deeper_headings_as_separate_slices(self) -> None:
        body = "## Slices\n### Only slice\n#### detail not a slice\n"

        spec = parse_spec(body)

        assert spec.items == [SliceSpecItem(title="Only slice", order=1, body="#### detail not a slice")]

    def test_should_return_empty_spec_when_no_slices_section(self) -> None:
        spec = parse_spec("## Goal\nJust a description without slices")

        assert spec.items == []

    def test_should_parse_declared_dependencies_from_the_depends_on_bullet(self) -> None:
        body = (
            "## Slices\n"
            "### First\n- **Type:** infra\n"
            "### Second\n- **Type:** vertical\n"
            "### Third\n- **Type:** vertical\n"
            "### Fourth\n- **Type:** vertical\n- **Depends on:** slices 1, 3\n"
        )

        spec = parse_spec(body)

        assert spec.items[3].depends_on == [1, 3]

    def test_should_parse_singular_and_plural_wording_the_same_way(self) -> None:
        singular = parse_spec("## Slices\n### First\n### Second\n- **Depends on:** slice 1\n")
        plural = parse_spec("## Slices\n### First\n### Second\n### Third\n- **Depends on:** slices 1, 2\n")

        assert singular.items[1].depends_on == [1]
        assert plural.items[2].depends_on == [1, 2]

    def test_should_declare_independence_when_bullet_says_none(self) -> None:
        spec = parse_spec("## Slices\n### First\n- **Depends on:** none\n")

        assert spec.items[0].depends_on == []

    def test_should_leave_the_declaration_undeclared_without_the_bullet(self) -> None:
        spec = parse_spec("## Slices\n### First\n- **Type:** infra\n")

        assert spec.items[0].depends_on is None

    def test_should_leave_the_declaration_undeclared_when_no_reference_points_backward(self) -> None:
        spec = parse_spec("## Slices\n### First\n- **Depends on:** slice 2\n### Second\n")

        assert spec.items[0].depends_on is None

    def test_should_ignore_the_literal_mentioned_inside_another_bullets_prose(self) -> None:
        spec = parse_spec(
            "## Slices\n### First\n### Second\n- **Scope:** check the bullet **Depends on:** of the Story\n"
        )

        assert spec.items[1].depends_on is None

    def test_should_ignore_stray_digits_that_are_not_the_documented_syntax(self) -> None:
        spec = parse_spec(
            "## Slices\n### First\n### Second\n### Third\n### Fourth\n- **Depends on:** none, see docs/adr/0001\n"
        )

        assert spec.items[3].depends_on == []

    def test_should_ignore_a_pr_number_mentioned_in_free_text(self) -> None:
        spec = parse_spec(
            "## Slices\n### First\n### Second\n### Third\n### Fourth\n- **Depends on:** PR #1 already merged\n"
        )

        assert spec.items[3].depends_on is None

    def test_should_discard_zero_since_it_never_points_to_a_real_slice(self) -> None:
        spec = parse_spec("## Slices\n### First\n### Second\n### Third\n- **Depends on:** slices 0, 1\n")

        assert spec.items[2].depends_on == [1]

    def test_should_deduplicate_repeated_positions(self) -> None:
        spec = parse_spec("## Slices\n### First\n### Second\n- **Depends on:** slices 1, 1\n")

        assert spec.items[1].depends_on == [1]

    _order_and_positions = st.integers(min_value=2, max_value=8).flatmap(
        lambda order: st.tuples(
            st.just(order),
            st.lists(st.integers(min_value=1, max_value=order - 1), max_size=order - 1),
        )
    )

    @given(order_and_positions=_order_and_positions)
    def test_every_parsed_position_points_to_an_earlier_slice(self, order_and_positions: tuple[int, list[int]]) -> None:
        order, positions = order_and_positions
        headings = "\n".join(f"### Slice {i}" for i in range(1, order))
        bullet = "none" if not positions else "slices " + ", ".join(str(position) for position in positions)
        body = f"## Slices\n{headings}\n### Last\n- **Depends on:** {bullet}\n"

        spec = parse_spec(body)

        parsed = spec.items[-1].depends_on
        assert parsed is not None
        assert all(1 <= position < order for position in parsed)

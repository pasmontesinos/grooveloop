from __future__ import annotations

from dataclasses import dataclass

from grooveloop.shared.domain.identifier import Identifier


@dataclass(frozen=True)
class SampleId(Identifier):
    pass


class TestIdentifier:
    def test_should_generate_distinct_identifiers(self) -> None:
        first = SampleId.generate()
        second = SampleId.generate()

        assert first != second

    def test_should_expose_value_as_string(self) -> None:
        identifier = SampleId(value="abc")

        assert str(identifier) == "abc"

    def test_should_be_equal_by_value(self) -> None:
        assert SampleId(value="abc") == SampleId(value="abc")

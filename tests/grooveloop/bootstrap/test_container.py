from __future__ import annotations

from grooveloop.bootstrap import container
from grooveloop.shared.infrastructure.target_repo import TargetRepo


class TestContainer:
    def test_should_restore_the_root_bindings_when_the_block_ends(self) -> None:
        container.bind(TargetRepo, TargetRepo("owner/before"))

        with container.restoring_bindings():
            container.bind(TargetRepo, TargetRepo("owner/inside"))
            inside = container.get(TargetRepo)

        assert inside == TargetRepo("owner/inside")
        assert container.get(TargetRepo) == TargetRepo("owner/before")

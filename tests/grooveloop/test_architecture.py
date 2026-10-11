from __future__ import annotations

import ast
from pathlib import Path

import grooveloop

_SOURCE_ROOT = Path(grooveloop.__file__).parent
_FEATURE_CONTEXTS = ["delivery", "slicing", "learning", "verification", "journal"]
_CONTEXTS = [*_FEATURE_CONTEXTS, "shared"]


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)

    return modules


def _violations(package: Path, forbidden_prefixes: list[str]) -> list[str]:
    return [
        f"{path.relative_to(_SOURCE_ROOT)} imports {module}"
        for path in sorted(package.rglob("*.py"))
        for module in _imported_modules(path)
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
    ]


def _layer_violations(layer: str, forbidden_layers: list[str]) -> list[str]:
    forbidden_prefixes = [
        f"grooveloop.{context}.{forbidden}" for context in _CONTEXTS for forbidden in forbidden_layers
    ]

    return [
        violation
        for context in _CONTEXTS
        for violation in _violations(_SOURCE_ROOT / context / layer, forbidden_prefixes)
    ]


class TestArchitecture:
    def test_should_keep_shared_free_of_feature_contexts(self) -> None:
        forbidden_prefixes = [f"grooveloop.{context}" for context in _FEATURE_CONTEXTS]

        assert _violations(_SOURCE_ROOT / "shared", forbidden_prefixes) == []

    def test_should_keep_each_feature_context_free_of_the_other_feature_contexts(self) -> None:
        violations = [
            violation
            for context in _FEATURE_CONTEXTS
            for violation in _violations(
                _SOURCE_ROOT / context,
                [f"grooveloop.{other}" for other in _FEATURE_CONTEXTS if other != context],
            )
        ]

        assert violations == []

    def test_should_keep_the_domain_free_of_application_and_infrastructure(self) -> None:
        assert _layer_violations("domain", ["application", "infrastructure"]) == []

    def test_should_keep_the_application_free_of_infrastructure(self) -> None:
        assert _layer_violations("application", ["infrastructure"]) == []

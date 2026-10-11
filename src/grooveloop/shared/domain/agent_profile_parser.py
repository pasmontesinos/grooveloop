from __future__ import annotations

from dataclasses import dataclass

_FENCE = "---"
_LIST_FIELDS = frozenset({"skills", "context_files"})


@dataclass(frozen=True)
class ParsedAgentProfile:
    name: str | None
    engine: str | None
    model: str | None
    skills: list[str] | None
    context_files: list[str] | None
    persona: str | None

    def merged_over(self, base: ParsedAgentProfile) -> ParsedAgentProfile:
        return ParsedAgentProfile(
            name=self.name if self.name is not None else base.name,
            engine=self.engine if self.engine is not None else base.engine,
            model=self.model if self.model is not None else base.model,
            skills=self.skills if self.skills is not None else base.skills,
            context_files=self.context_files if self.context_files is not None else base.context_files,
            persona=self.persona if self.persona is not None else base.persona,
        )


def parse_agent_profile(content: str) -> ParsedAgentProfile | None:
    lines = content.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        return None

    end = _closing_fence(lines)
    if end is None:
        return None

    fields = _parse_frontmatter(lines[1:end])
    persona = "\n".join(lines[end + 1 :]).strip() or None

    return ParsedAgentProfile(
        name=_as_scalar(fields.get("name")),
        engine=_as_scalar(fields.get("engine")),
        model=_as_scalar(fields.get("model")),
        skills=_as_list(fields.get("skills")),
        context_files=_as_list(fields.get("context_files")),
        persona=persona,
    )


def _closing_fence(lines: list[str]) -> int | None:
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            return index

    return None


def _parse_frontmatter(lines: list[str]) -> dict[str, str | list[str]]:
    fields: dict[str, str | list[str]] = {}
    current_list: str | None = None
    for raw in lines:
        item = _block_item(raw)
        if current_list is not None and item is not None:
            fields[current_list] = [*_ensure_list(fields.get(current_list)), item]
            continue

        current_list = None
        key, value = _split_key_value(raw)
        if key is None:
            continue

        if key in _LIST_FIELDS and value == "":
            fields[key] = []
            current_list = key
        else:
            fields[key] = value

    return fields


def _split_key_value(raw: str) -> tuple[str | None, str]:
    if ":" not in raw:
        return None, ""

    key, _, value = raw.partition(":")

    return key.strip(), value.strip()


def _block_item(raw: str) -> str | None:
    stripped = raw.strip()
    if stripped.startswith("- "):
        return stripped[2:].strip()

    return None


def _ensure_list(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return value

    return []


def _as_scalar(value: str | list[str] | None) -> str | None:
    if isinstance(value, str):
        return value

    return None


def _as_list(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None

    if isinstance(value, list):
        return value

    inner = value.strip()
    if not (inner.startswith("[") and inner.endswith("]")):
        return [inner]

    body = inner[1:-1].strip()
    if not body:
        return []

    return [part.strip() for part in body.split(",")]

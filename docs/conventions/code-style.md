# Code Conventions

## Critical Rules

- No relative imports.
- No comments in the code. The only exception is a tool pragma that cannot be avoided, written with its precise error code (`# type: ignore[method-assign]`, never a bare `# type: ignore`). Today there are three, and a new one needs the same justification:
  - `shared/application/commands/command_handler.py` and `shared/application/queries/query_handler.py`: `# type: ignore[method-assign]`, where `__init_subclass__` replaces `__call__` with its logged version.
  - `cli/story_selector.py`: `# type: ignore[misc]`, on `self.mutate_reactive(StorySelector.value)`, where mypy reports `misc` for the class-level Textual reactive passed as an argument.

  mypy runs with `warn_unused_ignores`, so a pragma that stops being needed fails `make check-types`.

## Imports

- `from __future__ import annotations` is the first line of every non-empty module, before any other import.
- ALWAYS at the top of the file, NEVER inside functions, methods or classes.
- Grouped in this order: (1) Standard library, (2) Third-party libraries, (3) Project modules (`grooveloop`, and `tests` in the test suite). Ruff `I` sorts them.
- Separate groups with a blank line.
- Imports used only in type annotations go in an `if TYPE_CHECKING:` block at the end of the import block, keeping the same internal order (stdlib, third-party, project). Ruff `TC` enforces it. The block is introduced only if there are type-only imports; it is not added empty "for consistency".
- `injector` resolves the dependencies of a provider from its annotations at runtime, so the types in the signature of a `@provider` or `@multiprovider` method are runtime imports. `pyproject.toml` lists both decorators in `runtime-evaluated-decorators`, so `TC` leaves those imports at runtime.

```python
# ✅ delivery/application/commands/mark_merged.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.shared.application.commands.command import Command
from grooveloop.shared.application.commands.command_handler import CommandHandler

if TYPE_CHECKING:
    from grooveloop.delivery.domain.slice_repository import SliceRepository
```

## Style

- Always apply *Modern Software Development* principles.
- In methods/functions, separate the `return` and logical blocks with a blank line.
- Use `list` by default for homogeneous collections of variable size (fields, parameters and return values), also in `frozen` dataclasses. Reserve `tuple` for fixed positional groupings (e.g. `tuple[int, int]`).
- Lines are at most 120 characters (`[tool.ruff] line-length`).

## Empty Files

Create empty `__init__.py` files with `bash touch` instead of `Write` to avoid showing unnecessary diffs in the IDE.

```bash
# ✅
touch path/to/__init__.py
```

## Anti-patterns

- ❌ Imports inside functions, methods or classes
- ❌ Type-only imports at runtime when they could go in `if TYPE_CHECKING:` — deferring them shrinks the runtime import graph and avoids cycles
- ❌ An empty `if TYPE_CHECKING:` block, or one with imports used at runtime
- ❌ Moving the annotation types of a `@provider` into `if TYPE_CHECKING:` — `injector` reads them at runtime
- ❌ A bare `# type: ignore`, or a pragma that a correct type would make unnecessary
- ❌ Using the `Write` tool to create empty `__init__.py` files — use `bash touch`
- ❌ `tuple[T, ...]` as a homogeneous collection (field, parameter or return value) — use `list[T]`, even in `frozen` dataclasses

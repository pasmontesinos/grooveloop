# ADR-0001: Hexagonal Python stack with a CLI, no Django/DRF

## Status

Accepted — 2026-06-22

## Context

The `grooveloop` repository was born by copying `CLAUDE.md` and `docs/conventions/*` from a Django/DRF project (`arcen_pi`). Those conventions describe a web API (DRF views, serializers, migrations, Docker Compose).

The real product is a different one: a **CLI orchestrator that drives the SDLC cycle of a change by delegating to agents**. It runs in the console, exposes no HTTP, and its persistence and agent execution must be able to change technology without touching the core.

## Decision

- **Language and runtime:** Python 3.13.
- **Architecture:** hexagonal (ports & adapters) with a pure domain core.
- **Base dependencies:** `injector` (DI), `uv` (environment and dependencies), `pytest` (tests), `mypy` (typing), `ruff` (lint + format).
- **Entrypoint:** local CLI (`uv run grooveloop ...`). **No Django, no DRF, no Docker** in v1.
- **Packaging:** `grooveloop` package under `src/grooveloop/`.

The hexagonal core is justified by **testability and evolvability**, not by scale: it allows changing the persistence adapter (GitHub → sqlite/postgres) and the agent execution adapter (Claude → codex/opencode/LLM-API) without touching domain or application. See [ADR-0004](0004-ports-and-adapters.md).

## Consequences

> **Update (2026-10):** The CLI surface is `loop`, `watch`, `doctor`, `usage`, `note` and `journal`; there are no `run`, `status` or `logs` commands. The runtime dependencies grew with `PyGithub`, `rich` and `textual` ([ADR-0007](0007-decoupled-execution-and-viewing-watch-in-textual.md)), and the loop calls `docker`, only if it is installed, to clean up what finished runs left behind; grooveloop itself still runs without containers. See [`infrastructure.md`](../conventions/infrastructure.md) and [`architecture.md`](../conventions/architecture.md).

- Everything specific to Django/DRF/Docker is removed from the conventions.
- The conventions describe commands and stack as a normative target; the scaffolding (`pyproject.toml`, `Makefile`, `src/` tree) arrives in the first implementation slice.
- The CLI documents an initial `run` / `status` / `logs` / `doctor` surface.

## Alternatives considered

- **Minimal Django only as an ORM:** rejected as premature and heavy for a CLI; the move to sqlite/postgres is solved by an adapter, not by dragging Django today.
- **Another language (Go/TypeScript):** rejected; it would mean redoing the conventions from scratch and discarding the carryover (all Python) from a previous orchestrator.

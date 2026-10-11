# ADR-0005: Context map (bounded contexts per SDLC process)

## Status

Accepted — 2026-06-22

## Context

The loop drives several processes of a change's life cycle: turning epics into User Stories, turning a User Story into a Spec, cutting the Spec into slices, and delivering each slice. Each process is a **subdomain** with its own language, its aggregates and its pace of evolution.

Initially a single `orchestration` context was proposed. Instead we decide to **split the bounded contexts per SDLC process**, so that each one evolves and is deployed independently and so that their boundaries are explicit.

## Decision

> **Update (2026-10):** The map has six contexts today: `slicing`, `delivery`, `verification` (deploy verification after the merge), `learning` (review lessons → convention changes), `journal` (the Story journal) and `shared`, each with its `infrastructure/di.py` module; `specification` and `discovery` are still not created. There is no `run` command: `cli/tick.py` is the composition root of a tick and `grooveloop loop` drives it. `shared` imports no feature context, a feature context imports no other, and `tests/grooveloop/test_architecture.py` enforces both and the layer rules. See [`architecture.md`](../conventions/architecture.md).

Bounded contexts, one per process:

| Process | Context | Status |
|---|---|---|
| Spec → sub-issues (slicing + order/dependencies) | `slicing` | **v1** |
| Deliver each slice (agent → PR → review → merge → advance) | `delivery` | **v1** |
| User Story → Spec | `specification` | future (map only) |
| Epic → User Stories | `discovery` | future (map only) |
| CQRS base, `Identifier`, `Clock`, `Event`, `EventDispatcher`, `QueryBus` | `shared` | v1 |

**v1 scope:** only `slicing`, `delivery` and `shared` are structured and implemented. `specification` and `discovery` are named in the map for orientation but **are not created** (folders, conventions or code) until the slice that tackles them — consistent with "do not anticipate future solutions".

**Aggregate ownership:**

- `slicing`: `Story` (parent Issue + `Spec` as a value object). It materializes the slices as sub-issues. Repo: `StoryRepository`.
- `delivery`: `Slice` (work-item with its state machine + `PullRequest` and comments). It drives each slice until the merge and advances to the next one. Repos: `SliceRepository`; `AgentRunner` port.
- The "Slice" concept is modeled **differently in each context**: in `slicing` it is born (sub-issue in `PENDING` with order/dependencies); in `delivery` it is the work-item with a life cycle. They share the identity (`SliceId` ↔ the GitHub sub-issue), not the class.

**Communication between contexts** (see `application.md` and [ADR-0006](0006-events-without-broker-detected-by-polling.md)):

- The `slicing → delivery` handoff happens via **GitHub state + detector**: `slicing` materializes the sub-issues; a detector observes them on the next tick and synthesizes the `Event` that `delivery` handles with its `EventHandler`. No event is published by the `slicing` command.
- Cross reads via `QueryBus` (Query/QueryResult promoted to `shared/application/queries/`).
- A context never imports the aggregates or repositories of another.

**Tick driver:** the `run` CLI command is the composition root of the tick; it coordinates the contexts (it invokes the command of the context in turn and/or pumps events). There is no "orchestrator" context that governs the others.

## Consequences

- Coordination between contexts is event-driven but **without a broker or persisted events**: detectors that query GitHub + in-process `EventDispatcher` (see [ADR-0006](0006-events-without-broker-detected-by-polling.md)). `shared` provides `Event`, `EventDispatcher` and the `EventHandler` base (no `EventProducer`/`EventCollector`).
- More boundaries and plumbing (events + QueryBus) than a single context; accepted for the clarity of subdomains and independent evolution.
- Each context carries its `infrastructure/di.py` (`SlicingModule`, `DeliveryModule`).

## Alternatives considered

- **A single `orchestration` context:** rejected because it mixes subdomains with different languages and paces in a single boundary.
- **Only `delivery` (slicing as an internal step):** rejected because it does not reflect that cutting is a process of its own that will later consume the output of `specification`.
- **Creating the 4 contexts now:** rejected because it anticipates the structure of processes not built yet.

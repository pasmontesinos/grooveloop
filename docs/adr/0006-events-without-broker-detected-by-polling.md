# ADR-0006: Events without a broker — detection by polling GitHub and an in-process dispatcher

## Status

Accepted — 2026-06-22

## Context

We want **event-driven** coordination between contexts (the tick reacts to "what has happened" instead of rediscovering ad hoc what to do each time), but **without a broker** or daemon, and running in CLI mode by ticks. We also do not want to persist events or couple their emission to the end of a command.

## Decision

> **Update (2026-10):** There is no `run` command: `grooveloop loop` drives `cli/tick.py`. Detectors also read the local run-dirs, not only GitHub, and they only read. The tick closes the abandoned runs before the detectors (`AgentRunAbandonedDetector` → `AgentRunAbandoned` → `CloseAgentRunCommandHandler`) and sweeps the finished worktrees after them (`AgentWorkspaceAbandonedDetector` → `RemoveAgentWorkspaceCommandHandler`). See [`infrastructure.md`](../conventions/infrastructure.md).

- **Events are not persisted** (there is no outbox and no "processed" cursor).
- **They are not published as the end of a command.** Aggregates **do not emit** events: there is no `EventProducer` or `EventCollector`.
- Events are **synthesized by detectors** (`detectors`, infrastructure) that **query GitHub** at the start of each tick and translate state conditions (predicates) into `Event`s of the domain vocabulary. Examples: `StoryReadyToSlice`, `SliceReadyToDispatch`, `PullRequestMerged`, `ReviewChangesRequested`.
- An **in-process `EventDispatcher`** (an `event type → handler(s)` registry, resolved with a `dict` and function calls; **it is not messaging**) delivers each `Event` to its `EventHandler`, which invokes the matching command.
- `Event` is a **`frozen` dataclass** (in-memory signal, no `channel` and no serialization: there is no broker). It is defined in the `domain/events.py` of the context that reacts.
- **No "processed" cursor:** idempotency + **state guards**. A condition already handled changes the state in GitHub (e.g. the slice moves from `PENDING` to `DISPATCHED`), so the detector stops emitting that event on the next tick. There is no need to mark events as processed.

Flow of the `run` tick (composition root, `grooveloop/cli/`):

```
1. Detectors: read GitHub → emit Event(s) for the actionable conditions
2. EventDispatcher: for each Event → EventHandler(s) → command
3. (bounded: one pass per tick; whatever is not handled is detected again on the next one)
```

## Consequences

- Zero messaging infrastructure and zero event state to maintain.
- **Natural recovery:** each tick re-detects the real GitHub state; a tick that dies halfway leaves no "lost" events, because the source is the state, not a queue.
- **Cost:** polling GitHub on each tick (no webhook; accepted, carryover §9).
- **Hard requirement:** the `EventHandler`s and the commands they invoke are **idempotent**; the state transitions act as a guard so work is not repeated.
- Consistent with [ADR-0003](0003-hybrid-state-and-log-instrumentation.md): GitHub is still the source of truth; the local event-log is still **only instrumentation** (it is not an outbox).
- Revises [ADR-0005](0005-context-map.md): the `slicing → delivery` handoff happens via **GitHub state + detector**, not via an event published by a `slicing` command.

## Alternatives considered

- **Broker / message queue:** rejected because it introduces infrastructure we do not want in a CLI.
- **Persistent outbox + relay in the tick:** rejected; it adds event state to maintain when the real state already lives in GitHub and re-detecting is enough.
- **Events emitted by the aggregate and published when the command closes:** rejected because it couples emission to the command and requires a producer/collector; we prefer detecting from GitHub.
- **In-process dispatch without events (the tick calls the commands directly after reading the state):** possible, but it loses the "detected condition → handler" decoupling that the event registry gives.

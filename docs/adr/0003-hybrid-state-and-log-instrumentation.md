# ADR-0003: Hybrid state (SoT in GitHub through a port) and instrumentation through logs

## Status

Accepted — 2026-06-22

## Context

On each tick, the loop needs to know which slices exist, their life cycle, their dependencies and the state of their PRs, to decide what to dispatch. The carryover from a previous orchestrator (§3) warns that **where the state's source of truth lives "colors everything"** and lays out three models:

- **A — Derived from GitHub:** stateless loop; each tick derives everything by reading GitHub. Maximum alignment with "everything in GitHub", but more calls and no compare-and-swap.
- **B — Local + mirror:** local event-log as the source of truth; GitHub only as output. Simple, but two sources of truth that diverge if the human touches GitHub.
- **C — Hybrid:** domain persisted through a port; local event-log only as audit.

## Decision

> **Update (2026-10):** There is no `~/.grooveloop/runs/{run-id}.jsonl` event-log and no per-step event record. The instrumentation is the `[ok]`/`[warn]`/`[fail]` lines of each command and the files under `~/.grooveloop/`: per run (`run.json`, `agent.log`, `agent.err`, `usage.json`, `turns.json`; run ids are `uuid4`) and per repo (`heartbeat.json`, `snapshot.json`, `pulls/<n>.json`, `stories/<n>/spec.md`). The handler base classes log through the standard `logging` module at `INFO`; the CLI writes those logs to stderr only when `GROOVELOOP_LOG_LEVEL` asks for them (default `WARNING`). The one piece of domain state outside GitHub is the Story journal, written by `JournalEntryRepository` under `stories/<n>/journal/`. The loop runs as a daemon that ticks every `--tick-interval` seconds, not on demand. See [`infrastructure.md`](../conventions/infrastructure.md).

We adopt the **hybrid model (C)**:

- The **domain source of truth** (Story, Slice, life cycle, dependencies, PR) is persisted **through the aggregate repositories (`StoryRepository`, `SliceRepository`)**. The GitHub adapters map that state to Issues, sub-issues, labels and Pull Requests. Switching to sqlite/postgres means switching adapters (see [ADR-0004](0004-ports-and-adapters.md)).
- The **local append-only event-log** (`~/.grooveloop/runs/{run-id}.jsonl`) is **instrumentation and audit**, not a source of truth.
- **Instrumentation = structured logs:** each loop step is recorded as an append-only event with provenance (timestamp, run-id, slice, phase). **No Prometheus, no mo-monitoring, no ORM transactions.** The state is *derived* from the port; the logs *document* what happened.

## Consequences

- The human and the loop share a single observable source of truth (GitHub), avoiding divergence.
- Instrumentation is light and portable; the event-log gives auditability and recoverability without coupling to metrics infrastructure.
- The cost is a higher number of reads to GitHub; it is bounded by the tick frequency (on-demand CLI in v1).

## Alternatives considered

- **A (derived from GitHub):** discarded as the only model because of the cost of deriving everything on each tick and the lack of CAS; part of its philosophy ("SoT in GitHub") is kept in C.
- **B (local + mirror):** discarded because it keeps two sources of truth and breaks when the human edits in the GitHub web UI.

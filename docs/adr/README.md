# Architecture Decision Records

Record of the architecture decisions of `grooveloop`. Each ADR captures a decision, its context and its consequences.

- [ADR-0001](0001-stack-python-hexagonal-cli.md) — Hexagonal Python stack with a CLI, no Django/DRF.
- [ADR-0002](0002-cqrs-commands-queries-querybus.md) — CQRS with commands/queries, handlers and QueryBus.
- [ADR-0003](0003-hybrid-state-and-log-instrumentation.md) — Hybrid state (SoT in GitHub through a port) and instrumentation through logs.
- [ADR-0004](0004-ports-and-adapters.md) — Ports and adapters of the orchestrator (one repository per aggregate: `StoryRepository`, `SliceRepository`; plus `AgentRunner`, `Clock`, probe/preflight).
- [ADR-0005](0005-context-map.md) — Context map: bounded contexts per SDLC process (`slicing`, `delivery`, `shared`; future `specification`, `discovery`).
- [ADR-0006](0006-events-without-broker-detected-by-polling.md) — Events without a broker: detection by polling GitHub + in-process `EventDispatcher` (no persistence, no emission in commands).
- [ADR-0007](0007-decoupled-execution-and-viewing-watch-in-textual.md) — Decoupled execution and viewing: the loop is headless and the Textual watch is the only viewer, with the state files as the contract.
- [ADR-0008](0008-the-loop-publishes-the-detail-the-cockpit-needs.md) — The loop publishes in state files the detail the watch cockpit needs (dependencies, Spec, open PRs), detected by change.
- [ADR-0009](0009-failed-is-terminal-with-bounded-retry-first.md) — `Failed` is terminal; before reaching it, the loop retries the recoverable causes with a cap (`--max-retries`, `retry:N`), and the final failure carries `failure:<cause>`.

# ADR-0002: CQRS with commands/queries, handlers and QueryBus

## Status

Accepted — 2026-06-22

## Context

The application layer needs a clear pattern for the orchestrator's use cases and for communication between contexts when the second one appears. We adopt the **CQRS** approach already validated in the conventions of a previous project, more explicit about intent (mutation vs read) and with a standard cross-context communication mechanism.

## Decision

> **Update (2026-10):** A query handler returns `XxxQueryResult`; it returns `XxxQueryResult | None` only when the absence is a real outcome (today only `GetStorySpecQueryHandler`). A promoted query keeps its handler in the provider context, and the domain → DTO mapping of a promoted result lives there, in `{dto}_dto_mapper.py`. Besides `commands/` and `queries/`, a context's `application/` may hold `tasks/` and `services/`. See [`application.md`](../conventions/application.md).

The application layer splits the use cases into **Commands** (mutate state) and **Queries** (read only), each with its **Handler**:

- **Commands:** `application/commands/{command_handler}.py`. `XxxCommand(Command)` (`frozen` dataclass) and `XxxCommandHandler(CommandHandler[XxxCommand, Result])` with `__call__(command) -> Result`. Commands carry **basic Python types** (not domain types, and not raw strings when a more precise basic type exists); the handler converts into domain types. Creation commands do not carry the ID (the aggregate generates it in `create()`).
- **Queries:** `Query`, `QueryResult` and `QueryHandler` in the **same file** `application/queries/{query_handler}.py`. `XxxQueryHandler(QueryHandler[XxxQuery, XxxQueryResult | None])` with `__call__(query)`.
- **Invocation:** the entrypoint gets the handler with `container.get(...)` and invokes it directly (`handler(command)`). There is no CommandBus.
- **Cross-context communication:**
  - *Reads:* `QueryBus`. The `Query` and its `QueryResult` are promoted to `shared/application/queries/`; the provider context registers the handler in the bus (`query_bus.register(...)` in `configure(binder)`); the consumer uses `query_bus.ask(...)`.
  - *Writes/reactions:* events **detected from GitHub** (no broker and no persistence, see [ADR-0006](0006-events-without-broker-detected-by-polling.md)) distributed by the `EventDispatcher` to an `EventHandler` (`{command}_when_{event}.py`) that invokes its own command handler. A command handler never calls another command handler.
- **Base classes** (`Command`, `CommandHandler`, `Query`, `QueryResult`, `QueryHandler`, `QueryBus`) live in the `shared` context.

Instrumentation through logs (ADR-0003) is kept: the `CommandHandler`/`QueryHandler` base classes instrument `__call__` automatically (via `__init_subclass__`), without a decorator.

## Consequences

> **Update (2026-10):** There are six contexts (`slicing`, `delivery`, `verification`, `learning`, `journal`, `shared`), not a single `orchestration` one, and the `QueryBus` carries the reads between them. The bus is typed: `Query[R]` declares its result and `ask[R](query: Query[R]) -> R` returns it, so `| None` remains only where the handler can return `None` (`GetStorySpecQuery`). See [`architecture.md`](../conventions/architecture.md).

- The `application/` structure is organized into `commands/` + `queries/`.
- The CQRS base classes are introduced in `shared` (part of the first scaffolding slice that needs them).
- The `QueryBus` is documented even though in v1 there is a single context (`orchestration`): it is the mechanism to use when the second one appears.
- More explicit intent and traceability; somewhat more ceremony per use case (Command + Handler).

## Alternatives considered

- **A single use case concept without distinguishing read/write:** rejected because it loses the mutation/read distinction and offers no standard cross-context communication mechanism.
- **Adding a CommandBus besides the QueryBus:** rejected as unnecessary; the entrypoint invokes the command handler directly, as in that project.

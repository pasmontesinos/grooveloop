# Application Layer

Use cases follow **CQRS**: they are split into **Commands** (mutate state) and **Queries** (read only), each with its **Handler**. See [ADR-0002](../adr/0002-cqrs-commands-queries-querybus.md). The base classes (`Command`, `CommandHandler`, `Query`, `QueryResult`, `QueryHandler`, `QueryBus`) live in `shared/application/`. Besides `commands/` and `queries/`, a context may have `tasks/` (builders of agent instructions) and `services/` (application services shared by several command handlers); see `architecture.md`.

## Commands

**Rule:** `XxxCommand(Command)` is a `frozen` dataclass and `XxxCommandHandler` inherits from `CommandHandler[XxxCommand, Result]`. Both live in `{context}/application/commands/{command}.py`, the command name in snake_case without the suffix (`mark_merged.py` holds `MarkMergedCommand` and `MarkMergedCommandHandler`). The handler orchestrates; the aggregate decides. The main method is `__call__(command) -> Result`. Every command handler today returns `None`: a command reports nothing back, and the next tick observes its effect in GitHub.

**Rule:** Creation commands **do not receive the ID** of the entity to create. The aggregate's factory sets its identity (`Lesson.create(...)` leaves it to GitHub, `JournalEntry.write(...)` generates it). The command only carries the business data it needs.

**Rule:** Commands carry **basic Python types** (`str`, `int`, `bool`, `datetime`, lists of them, or a `TypedDict` of them such as `RefineConventionsComment`), never domain types, and never raw strings when a more precise basic type exists. The entrypoint (CLI command, event handler) passes basic types; the handler converts them into domain types.

| Layer | Types | Example |
|------|-------|---------|
| Infra → Command | domain → basic | `MarkMergedCommand(slice_id=event.slice_id.value)` in the event handler; `argparse` `type=int` for `--story` |
| Command | `str`, `int`, `bool` | Carries without transforming |
| Handler → Domain | `str` → `SliceId`, `str` → `EntryKind` | `SliceId(command.slice_id)` in the handler |

```python
# ✅ slicing/application/commands/create_slices_from_spec.py
@dataclass(frozen=True)
class CreateSlicesFromSpecCommand(Command):
    story_id: str
    verify_deploy: bool = False


class CreateSlicesFromSpecCommandHandler(CommandHandler[CreateSlicesFromSpecCommand, None]):
    def __init__(self, story_repository: StoryRepository) -> None:
        self._story_repository = story_repository

    def __call__(self, command: CreateSlicesFromSpecCommand) -> None:
        story = self._story_repository.find(StoryId(command.story_id))
        if story is None:
            raise StoryNotFoundError(f"Story {command.story_id} not found")

        story.materialize_slices(verify_deploy=command.verify_deploy)

        self._story_repository.save(story)
```

The handler lives in `slicing` and only uses `slicing` ports (`StoryRepository`): the `Story` aggregate materializes the sub-issues and they are persisted in GitHub. **It does not publish events or use `SliceRepository`** (that belongs to `delivery`). The handoff to `delivery` is done by a detector that observes those sub-issues on the next tick (see [ADR-0006](../adr/0006-events-without-broker-detected-by-polling.md)).

### Idempotent handlers

**Rule:** A command can arrive twice for the same condition (two ticks detect it before the state changes, or a tick dies halfway), so every handler is idempotent. It loads the aggregate and **returns early** when the guard of the aggregate says the transition no longer applies; only then does it act and save.

```python
# ✅ delivery/application/commands/mark_merged.py
def __call__(self, command: MarkMergedCommand) -> None:
    a_slice = self._slice_repository.find(SliceId(command.slice_id))
    if a_slice is None or not a_slice.can_be_merged():
        return

    a_slice.mark_merged()
    self._slice_repository.save(a_slice)
```

- A missing aggregate is an early return too, except when the event that triggered the command guarantees it exists (`CreateSlicesFromSpecCommandHandler` raises `StoryNotFoundError`).
- A handler that starts an agent checks its guards **before** dispatching (`DispatchSliceCommandHandler` returns early when the slice is no longer `PENDING`, when the Story reached its `ParallelSliceLimit` or when the profile is missing), so a repeated command never launches a second run.
- The recovery handlers (`RelaunchImplementationCommandHandler`, `ResumeReviewPhaseCommandHandler`...) also return early when the slice's `run:<id>` is no longer the run the event named, so two ticks on the same interrupted run dispatch again only once.

## Queries (same context)

**Rule:** `XxxQuery`, `XxxQueryResult` and `XxxQueryHandler` are defined in the **same file**: `{context}/application/queries/{query}.py`, the result before the query. `Query` is generic in its result: the query declares it (`XxxQuery(Query[XxxQueryResult])`, `GetStorySpecQuery(Query[GetStorySpecQueryResult | None])`), so the `QueryBus` returns that type. The handler inherits from `QueryHandler[XxxQuery, XxxQueryResult]`, with the same result type the query declares, and its main method is `__call__(query) -> XxxQueryResult`. It returns `XxxQueryResult | None` only when the absence is a real outcome of the question; today only `GetStorySpecQueryHandler` does, because the Story may not exist. An empty answer is an empty list in the result, not `None`.

**Rule:** When `XxxQueryResult` holds DTOs built from aggregates of the same context, the mapping lives as a `@classmethod from_domain(cls, entity) -> Self` of the DTO. The handler has no private mapping helpers.

```python
# ✅ delivery/application/queries/next_dispatchable_slices.py
@dataclass(frozen=True)
class DispatchableSliceDTO:
    id: str

    @classmethod
    def from_domain(cls, a_slice: Slice) -> Self:
        return cls(id=a_slice.id.value)


@dataclass(frozen=True)
class NextDispatchableSlicesQueryResult(QueryResult):
    slices: list[DispatchableSliceDTO]


@dataclass(frozen=True)
class NextDispatchableSlicesQuery(Query[NextDispatchableSlicesQueryResult]):
    story_id: str


class NextDispatchableSlicesQueryHandler(QueryHandler[NextDispatchableSlicesQuery, NextDispatchableSlicesQueryResult]):
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def __call__(self, query: NextDispatchableSlicesQuery) -> NextDispatchableSlicesQueryResult:
        slices = self._slice_repository.search(story_id=StoryId(query.story_id))
        dispatchable = [a_slice for a_slice in slices if a_slice.is_dispatchable(slices)]

        return NextDispatchableSlicesQueryResult(
            slices=[DispatchableSliceDTO.from_domain(a_slice) for a_slice in dispatchable]
        )
```

## Communication between contexts

There are six contexts (`slicing`, `delivery`, `verification`, `learning`, `journal`, `shared`; see [ADR-0005](../adr/0005-context-map.md)). A feature context never imports another one. Cross-context communication is modeled like this:

### Reads: QueryBus

**Rule:** If another context needs the query, promote `XxxQuery`, `XxxQueryResult` and its DTOs to `shared/application/queries/{query}.py`, as plain `frozen` dataclasses of basic types. The handler stays in the provider context, in `{context}/application/queries/{query}.py`, and imports the promoted types. The provider registers it in the `QueryBus` from its DI module. The consumer uses `query_bus.ask(...)`.

**Rule:** A promoted DTO cannot have `from_domain`: `shared` does not import feature contexts. The mapping lives in the provider context, in `{context}/application/queries/{dto}_dto_mapper.py`, as a function `{dto}_dto_from_domain(entity) -> DTO` (`journal_entry_dto_from_domain`, `pending_lesson_dto_from_domain`, `agent_session_dto_from_domain`).

```python
# ✅ shared/application/queries/read_journal_entries.py
@dataclass(frozen=True)
class JournalEntryDTO:
    kind: str
    author: str
    body: str
    written_at: str


@dataclass(frozen=True)
class ReadJournalEntriesQueryResult(QueryResult):
    entries: list[JournalEntryDTO]


@dataclass(frozen=True)
class ReadJournalEntriesQuery(Query[ReadJournalEntriesQueryResult]):
    repo: str
    story_id: str
    kinds: list[str] | None = None
    written_after: datetime | None = None
```

```python
# ✅ journal/application/queries/journal_entry_dto_mapper.py
def journal_entry_dto_from_domain(entry: JournalEntry) -> JournalEntryDTO:
    return JournalEntryDTO(
        kind=entry.kind.value,
        author=entry.author,
        body=entry.body,
        written_at=entry.written_at.isoformat(),
    )
```

```python
# ✅ registration in the DI of the provider context (journal owns JournalEntry)
class JournalModule(Module):
    def configure(self, binder: Binder) -> None:
        query_bus = resolve(binder.injector, QueryBus)
        query_bus.register(ReadJournalEntriesQuery, ReadJournalEntriesQueryHandler)
```

```python
# ✅ use from a consumer in another context (delivery/application/tasks/story_journal_section.py)
def build(self, repo: str, story_id: str) -> str:
    result = self._query_bus.ask(ReadJournalEntriesQuery(repo=repo, story_id=story_id))
    if not result.entries:
        return ""
```

- `QueryBus.ask[R](query: Query[R]) -> R` returns the result type the query declares. The consumer neither annotates the variable nor handles a `None` the handler cannot return; it handles `None` only when the query declares `| None` (today only `GetStorySpecQuery`, in `ImplementationTask`).
- A query that only its own context uses stays in that context. It is still registered in the `QueryBus` when a piece of that context asks through the bus (`SliceReadyToDispatchDetector` asks `NextDispatchableSlicesQuery`).
- `ListLoopsQuery` reads only `shared` ports, so its handler lives in `shared/application/queries/list_loops.py`, next to the query.

### Writes / reactions: events detected from GitHub

A context reacts to what happens in another **without a broker and without persisting events** (see [ADR-0006](../adr/0006-events-without-broker-detected-by-polling.md)):

- Aggregates **do not emit** events; commands **do not publish** events when they finish.
- On each tick, **detectors** (infrastructure) read GitHub or the local run-dirs and synthesize `Event`s for the actionable conditions.
- An in-process **`EventDispatcher`** delivers each `Event` to its `EventHandler`, which invokes the matching command.
- Idempotency + state guards: a condition already handled stops being detected on the next tick.

See `Event` in `domain.md` and the detectors and event handlers in `infrastructure.md`. **A command handler never invokes another command handler directly.** What several handlers share goes in an application service (`application/services/`).

## Instrumentation

**Rule:** The `CommandHandler`/`QueryHandler` base classes wrap `__call__` in `__init_subclass__` and log every execution with the standard `logging` module at `INFO`: `Executing <name> with <vars(command)>` before and `Executed <name> in <ms>ms` after. **There is no decorator**, and a handler adds nothing to be instrumented. `cli/main.py` sends the `grooveloop` logs to stderr at the level of `GROOVELOOP_LOG_LEVEL` (default `WARNING`), so these records show only with `GROOVELOOP_LOG_LEVEL=INFO` (see `infrastructure.md`).

The operational record of what the loop does is not this log: it is the `[ok]`/`[warn]`/`[fail]` lines of each command and the files under `~/.grooveloop/` (see `infrastructure.md` and [ADR-0003](../adr/0003-hybrid-state-and-log-instrumentation.md)). No metrics, no Prometheus.

```python
# ✅ instrumented automatically by the base class; no decorator
class MarkMergedCommandHandler(CommandHandler[MarkMergedCommand, None]):
    def __call__(self, command: MarkMergedCommand) -> None: ...
```

## Anti-patterns

- ❌ A command handler invokes another command handler — share the logic through an application service or let the next tick detect the new state.
- ❌ Passing the entity ID in a creation command — the aggregate's factory sets its identity.
- ❌ Using a domain type (VO, enum) or a raw `str` in a Command/Query when a more precise basic Python type exists — infra passes basic types, the handler converts to domain.
- ❌ A handler that acts without first checking the aggregate's guard — the command can arrive twice.
- ❌ `XxxQueryResult | None` when the absence is not a real outcome — return the result with an empty list.
- ❌ A `Query` subclass that does not declare its result type (`Query` bare), or a consumer that checks `None` on a result whose query does not declare `| None`.
- ❌ `Query`/`QueryResult` in `shared` when only its own context uses it.
- ❌ `from_domain` on a promoted DTO, or a promoted DTO that imports a feature domain — the mapping lives in the provider's `{dto}_dto_mapper.py`.
- ❌ Private `_to_dto` helper in the handler — the mapping lives in `DTO.from_domain` or in the mapper module.
- ❌ Handler that depends on a concrete adapter (`GithubStoryRepository`, `SubprocessAgentRunner`) instead of the port.
- ❌ Reimplementing the handler logging by hand or not inheriting from `CommandHandler`/`QueryHandler`.
- ❌ Emitting metrics from a handler.

# Architecture and Tech Stack

## Language and Tools

- Python 3.13.
- Hexagonal architecture (ports & adapters) with a pure domain core. See [ADR-0001](../adr/0001-stack-python-hexagonal-cli.md).
- Frozen `dataclasses` (no pydantic) for DTOs, commands, queries, value objects and events.
- `typing` (`Self`, `Protocol`, `TypedDict`, `TYPE_CHECKING`...) and PEP 695 generics (`class CommandHandler[C, CR](ABC)`).
- `abc` for interfaces (ports).
- `injector` for dependency injection.
- `PyGithub` (REST and GraphQL) for GitHub, `rich` and `textual` for the `watch` terminal app.
- `pytest`, `hypothesis` and `unittest.mock` for tests.
- `uv` for environment and dependencies, `mypy` (strict) for static typing, `ruff` for linting and formatting.
- Agents run as a detached subprocess (`start_new_session=True`, a new POSIX session).
- **No web framework and no database.** The entrypoint is a local CLI (`grooveloop`, `cli/main.py`). At runtime the loop calls `git`, `gh` (for its token), the agent engine and, only to clean up finished runs and only if it is installed, `docker`.

## Folder structure

```
src/grooveloop/
  bootstrap/                      # the container: Container, the list of modules, the global `container`
  cli/                            # composition root: main, tick, loop, watch, doctor, preflight, the watch panels
  {context}/
    domain/
      {aggregate}.py
      {entity}.py
      {value_object}.py
      {enum}.py
      {aggregate}_repository.py   # port, one per aggregate
      {port}.py                   # any other port
      events.py                   # only if the context reacts to events
      exceptions.py
    application/
      commands/
        {command}.py              # XxxCommand + XxxCommandHandler
      queries/
        {query}.py                # XxxQuery + XxxQueryResult + XxxQueryHandler (or only the handler of a promoted query)
        {dto}_dto_mapper.py       # domain → DTO mapping of a promoted query result
      tasks/
        {name}_task.py            # builder of an agent instruction: build(...) and resumption(...)
      services/
        {service}.py              # application service shared by several command handlers
    infrastructure/
      di.py                       # the context's injector Module
      cli/
        {command}_command.py      # a CLI command that belongs to this context
      detectors/
        {event}_detector.py
        {condition}_outcome_detector.py
      event_handlers/
        {command}_when_{event}.py
      {prefix}_{port}.py          # adapters (github_slice_repository.py, local_agent_session_repository.py...)
      {input}.py                  # value object of a CLI input bound at startup (max_review_rounds.py...)
tests/
  grooveloop/                     # mirrors src/grooveloop/
    {context}/
      domain/
      application/{commands,queries}/
      infrastructure/{cli,detectors,event_handlers}/
      mothers/{entity}_mother.py
    cli/
    bootstrap/
    test_architecture.py
  playground/shared/infrastructure/
    fake_{port}.py                # shared fakes of the ports
```

- CQRS use cases: `application/commands/` (mutate state) and `application/queries/` (read). See [ADR-0002](../adr/0002-cqrs-commands-queries-querybus.md) and `application.md`.
- `application/tasks/` holds the builders of the instruction text that a command hands to an agent (`ImplementationTask`, `ReviewTask`, `AddressingTask`, `VerificationTask`, `RefinementTask`). Each one exposes `build(...)` for a new run and, when the phase can be resumed, `resumption(...)` for a resumed one. A task may read other contexts through the `QueryBus` (`ImplementationTask` asks for the Story's Spec; `StoryJournalSection`, the journal block shared by two tasks, asks for the journal). It never mutates state.
- `application/services/` holds the application services shared by several command handlers of the same context (`SliceRetry`, `ImplementationRecovery`, `ReviewPhaseRecovery`, `AgentRunFailureCause`, `VerificationRetry`, `VerificationRecovery`). A service depends on ports, never on another handler.
- A context creates `tasks/` or `services/` only when it has one.
- CLI command modules carry the `_command` suffix. A command that belongs to one context lives in its `infrastructure/cli/` (`usage`, `note`, `journal`); the ones that coordinate contexts live in the top-level `cli/` (`loop`, `watch`, `doctor`).
- Adapters carry the prefix of their implementation: `github_`, `claude_`, `opencode_`, `subprocess_`, `local_` (run-dirs under `~/.grooveloop/runs/`), `filesystem_` (state files under `~/.grooveloop/repos/`), `docker_`, `signal_`, `system_`, `injector_`, `mapped_` and `cached_`. Probes end in `_probe`. Test fakes carry `fake_`.
- Each port in its own file.
- Introduce `domain/events.py`, `infrastructure/detectors/` and `infrastructure/event_handlers/` only when the context reacts to events.

## Layer rules

`tests/grooveloop/test_architecture.py` parses every module of `src/grooveloop/` and fails when:

- `shared` imports any feature context (`delivery`, `slicing`, `learning`, `verification`, `journal`);
- a feature context imports another feature context (there is no exception: cross-context reads go through the `QueryBus` with the promoted queries of `shared/application/queries/`);
- a `domain/` package imports an `application/` or `infrastructure/` package (of any context);
- an `application/` package imports an `infrastructure/` package (of any context).

Communication between feature contexts goes through the `QueryBus` and through events (see `application.md`). Only the composition root (`cli/`, `bootstrap/`) imports several contexts; the test does not check it.

## Context map

Bounded contexts are split **per delivery process** (see [ADR-0005](../adr/0005-context-map.md)):

| Context | Process | Aggregates and ports |
|---|---|---|
| `slicing` | Spec → sub-issues, with order and dependencies; closes the Story once every slice is merged and no verification or lesson of the Story is pending. | `Story` (+`Spec`, + the `Slice` it materializes); `StoryRepository`. |
| `delivery` | Drives each slice: agent → PR → automatic review → corrections → merge. Closes abandoned runs and sweeps finished worktrees. | `Slice` (+`PullRequest`); `SliceRepository`, `SliceLabels`, `PullRequestMerger`, `DirectiveMarker`; query port `AgentSessionRepository`. |
| `verification` | After the merge of a slice labeled `verify-deploy`, the verifier agent checks the deploy and the increment. | `SliceVerification`; `SliceVerificationRepository`, `MergedSliceSignal`. |
| `learning` | The `/grooveloop-learn` comments of a merged PR become a lesson, one per capture of the comments not captured yet; the scribe agent turns it into a conventions PR. | `Lesson`; `LessonRepository`, `LearnSignal`, `LessonCommentMarker`, `RefinementResult`, `ConventionsPullRequestStatus`. |
| `journal` | The Story journal that agents and humans write with `note` and read with `journal`. | `JournalEntry`; `JournalEntryRepository`, `AgentRunContextRepository`. |
| `shared` | Common base (below). | — |

- The "Slice" concept is modeled differently in `slicing` (an item of the Spec that becomes a sub-issue), in `delivery` (the work item with its life cycle) and in `verification` (the verification of a merged slice). Each context declares its own `SliceId` and `StoryId` classes; they share the value (the issue number), not the class.
- The `slicing → delivery` handoff is GitHub state: `slicing` creates the sub-issues and, on the next tick, `SliceReadyToDispatchDetector` (in `delivery`) finds the dispatchable ones. No event is published by a command.

See ports and adapters in [ADR-0004](../adr/0004-ports-and-adapters.md): one repository per aggregate; the `PullRequest` lives inside the `Slice` aggregate (no repository of its own).

## `shared` context

It holds what several contexts use. It never imports a feature context.

- **Application:** base classes `Command`, `CommandHandler` (`commands/`), `Query`, `QueryResult`, `QueryHandler`, `QueryBus` (`queries/`), `EventDispatcher` and `EventHandler` (`events/`) and the `Probe` port of the preflight (`probes/`). The promoted cross-context queries live in `shared/application/queries/` (`GetStorySpecQuery`, `AllSlicesMergedQuery`, `StoryPullRequestNumbersQuery`, `ListRepoSessionsQuery`, `PendingLessonsQuery`, `UncapturedLessonsQuery`, `PendingVerificationsQuery`, `ReadJournalEntriesQuery`). `ListLoopsQuery` is the exception: it reads only `shared` ports, so its handler lives next to it.
- **Domain:** `Identifier` (base of the `{Entity}Id`s, with `generate()`), the `Event` base (`frozen` dataclass), the value objects several contexts share (`AgentRun`, `AgentRunVerdict`, `AgentRunCause`, `RetryPolicy`, `AgentProfile`, the snapshot types the `watch` reads...) and the common ports: `Clock`, `AgentRunner`, `AgentRunnerRegistry`, `AgentCommand`, `AgentLogReader`, `AgentProfiles`, `AgentRunLogs`, `AgentWorkspaces`, `AbandonedAgentRuns`, `WorkspaceProcesses`, `WorkspaceContainers`, `ProcessLiveness`, `LoopPresence`, `LoopSnapshots`, `PullRequestDetails` and `StorySpecs`. There is **no** `EventProducer` or `EventCollector`: events are synthesized by detectors and distributed by the in-process `EventDispatcher` (no broker and no persistence, see [ADR-0006](../adr/0006-events-without-broker-detected-by-polling.md)).
- **Infrastructure:** the adapters of those ports, the probes, the GitHub client helpers (`GithubStoryGraph`, `GithubGraphQL`, `GithubReadCache`), the `ExitCode` of every command (`cli/exit_code.py`), the packaged agent profiles (`agent_profiles/*.md`) and `SharedModule`.

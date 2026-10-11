# Dependency Injection

## Bootstrap

The main configuration lives in `src/grooveloop/bootstrap/`:

- `di.py`: the list of `injector` modules that make up the root injector: `SharedModule`, `SlicingModule`, `DeliveryModule`, `LearningModule`, `VerificationModule`, `JournalModule`.
- `_container.py`: the `Container` class that wraps `injector.Injector`. `initialize(modules)` creates the root injector with `auto_bind=False`; `bind(interface, implementation)` binds a value in it; `get(interface)` resolves; `override(...)` and `restoring_bindings()` exist only for tests.
- `__init__.py`: creates the global `container`, initializes it with the modules from `di.py` and exports it.

## Modules

- Each context has its own `infrastructure/di.py` with an `injector.Module` (`SlicingModule`, `DeliveryModule`, `VerificationModule`, `LearningModule`, `JournalModule`); the common ports (`Clock`, `AgentRunner`, `AgentRunnerRegistry`, `QueryBus`, `EventDispatcher`, the `Github` client...) and the shared probes are provided by `SharedModule` (`shared/infrastructure/di.py`).
- A module binds ports to adapters with `@provider` methods and registers its event handlers and its promoted query handlers in `configure(binder)`.

## Providers

**Rule:** Define `@provider` methods that bind interfaces (ports) to concrete implementations (adapters), and that build the concrete classes the entrypoints ask for (command and query handlers, detectors, tasks, services, probes). A provider method is named after what it provides, in snake_case and without a prefix (`slice_repository`, `dispatch_slice_command_handler`, `pull_request_merged_detector`).

**Rule:** A provider that must return the same instance across the process is also decorated with `@singleton`: today the `Clock`, `RunsDir`, `ReposDir`, the log readers, the `GithubReadCache` shared by every reader of a tick, the query and event handler registries and the `Github` client.

```python
# ✅ grooveloop/slicing/infrastructure/di.py
class SlicingModule(Module):
    @provider
    def story_repository(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> StoryRepository:
        return GithubStoryRepository(target_repository(github, target_repo, cache), cache)

    @provider
    def create_slices_from_spec_command_handler(
        self, story_repository: StoryRepository
    ) -> CreateSlicesFromSpecCommandHandler:
        return CreateSlicesFromSpecCommandHandler(story_repository=story_repository)
```

```python
# ✅ grooveloop/delivery/infrastructure/di.py
class DeliveryModule(Module):
    @provider
    def slice_repository(self, github: Github, target_repo: TargetRepo, cache: GithubReadCache) -> SliceRepository:
        return GithubSliceRepository(target_repository(github, target_repo, cache), cache)

    @provider
    def dispatch_slice_command_handler(
        self,
        slice_repository: SliceRepository,
        agent_runner_registry: AgentRunnerRegistry,
        agent_profiles: AgentProfiles,
        slice_labels: SliceLabels,
        implementation_task: ImplementationTask,
    ) -> DispatchSliceCommandHandler:
        return DispatchSliceCommandHandler(
            slice_repository=slice_repository,
            agent_runner_registry=agent_runner_registry,
            agent_profiles=agent_profiles,
            slice_labels=slice_labels,
            implementation_task=implementation_task,
        )
```

**Rule:** An adapter or an event handler that needs an input value from the CLI (the target repo, the workdir, the verification flag, the round and retry caps...) asks for it as a value object in its `@provider` (or with `container.get(...)` in the event handler) and resolves the external object inside. The entrypoint binds those value objects **only once at startup**, with `container.bind(...)`. Never declare a `@provider` with a fake default value (`TargetRepo(value="")`) just so the binding exists.

```python
# ✅ grooveloop/cli/invocation_inputs.py
def bind_invocation_inputs(
    repo_full_name: str,
    workdir: str,
    *,
    verify_deploy: bool = False,
    max_review_rounds: int = 0,
    max_parallel_slices: int = 1,
    journal_enabled: bool = False,
    max_retries: int = 0,
    auto_merge: bool = False,
) -> None:
    container.bind(TargetRepo, TargetRepo(repo_full_name))
    container.bind(AgentWorkdir, AgentWorkdir(workdir))
    container.bind(VerifyDeploy, VerifyDeploy(verify_deploy))
    container.bind(MaxReviewRounds, MaxReviewRounds(max_review_rounds))
    container.bind(MaxParallelSlices, MaxParallelSlices(max_parallel_slices))
    container.bind(JournalEnabled, JournalEnabled(journal_enabled))
    container.bind(MaxRetries, MaxRetries(max_retries))
    container.bind(AutoMerge, AutoMerge(auto_merge))
```

`loop` and `tick` call it; `doctor` binds only `AgentWorkdir` and, with `--repo`, `TargetRepo`.

**Rule:** `EventHandler`s are registered with `bind_event_handlers(binder, {...})` (`shared/infrastructure/event_handler_binding.py`) inside `configure(binder)`, mapping each event type to its handler. The helper does two inseparable things: it registers the handler in the `EventDispatcher` **and** binds it in the binder. The root injector is created with `auto_bind=False`, so it does not know how to build a class nobody has bound. The loop runs in the root injector, so registering without binding breaks event delivery.

```python
# ✅ grooveloop/slicing/infrastructure/di.py
class SlicingModule(Module):
    def configure(self, binder: Binder) -> None:
        query_bus = resolve(binder.injector, QueryBus)
        query_bus.register(GetStorySpecQuery, GetStorySpecQueryHandler)

        bind_event_handlers(
            binder,
            {
                StoryReadyToSlice: CreateSlicesFromSpecWhenStoryReadyToSlice,
                StoryCompleted: CompleteStoryWhenStoryCompleted,
            },
        )

    @provider
    def get_story_spec_query_handler(self, story_repository: StoryRepository) -> GetStorySpecQueryHandler:
        return GetStorySpecQueryHandler(story_repository=story_repository)
```

**Rule:** For the queries other pieces ask through the bus, the provider context registers the handler in the `QueryBus` inside `configure(binder)`, besides declaring its `@provider` (see the example above).

**Rule:** Inside a module, resolve an abstract port from the binder's injector with `resolve(binder.injector, QueryBus)` (`shared/infrastructure/injector_lookup.py`), not with `binder.injector.get(QueryBus)`. `Injector.get` is typed to take a concrete class, so passing an ABC makes mypy report `type-abstract`; `resolve` accepts any callable type and keeps the return type, with no pragma.

## Usage

**Rule:** Use `container.get(MyDependency)` in entrypoints (CLI commands, the tick, event handlers) to get instances. `Container.get` has an `Any` overload, so it accepts an abstract port without a mypy error.

```python
# ✅ grooveloop/delivery/infrastructure/cli/usage_command.py
def run(repo: str, slice_number: int) -> int:
    handler = container.get(ListSliceSessionsQueryHandler)
    result = handler(ListSliceSessionsQuery(repo=repo, slice_id=str(slice_number)))
    ...
```

## Testing

**Rule:** `container.override(interface, implementation)` is **exclusive to tests**. It is used as a context manager to replace dependencies. No file in `src/` calls it: production code is wired with `@provider` and, for the CLI input values, with `container.bind(...)` in the entrypoint.

The override opens a child injector with `create_child_injector`, which does **not** propagate the root's `auto_bind=False`. A missing binding is auto-built inside the `with` and blows up outside it, so using it in production hides wiring gaps instead of flagging them.

**Rule:** `container.bind(...)` in an entrypoint test writes to the root injector. `tests/conftest.py` wraps every test in `container.restoring_bindings()` (autouse), which snapshots the root bindings and restores them afterwards, so one test's bindings never leak into the next. The same `conftest.py` overrides, for every test, the ports that would touch the real machine (`AgentWorkspaces`, `AbandonedAgentRuns`, `WorkspaceProcesses`, `WorkspaceContainers`, `PullRequestDetails`, `StorySpecs`) with their shared fakes, and flushes the `GithubReadCache`.

## TDD workflow with DI

**Rule:** When adding dependencies to a use case during TDD, follow this order: (1) Update the provider in `infrastructure/di.py`, (2) Change the use case constructor, (3) Write the test with the dependencies mocked or faked.

`tests/grooveloop/shared/infrastructure/test_container_wiring.py` and the `test_di.py` of `slicing`, `delivery`, `verification` and `learning` resolve wired classes from the real container. They cover part of the wiring, not every provider; the entrypoint tests, which run in the real container, cover the rest of what they reach.

## Anti-patterns

- ❌ Calling `dispatcher.register(...)` directly in `configure` — the handler stays unbound and the root injector does not know how to build it; use `bind_event_handlers`.
- ❌ `binder.injector.get(<ABC>)` with a `# type: ignore[type-abstract]` — use `resolve(binder.injector, <ABC>)`.
- ❌ `container.override(...)` or `container.restoring_bindings()` in `src/` — they are exclusive to tests; production wiring goes in `@provider` and the CLI input value in the entrypoint's `container.bind(...)`.
- ❌ `@provider` that returns a fake default value (`TargetRepo(value="")`) only so the binding exists — the entrypoint binds the real value at startup.
- ❌ A `provide_` prefix in provider names.

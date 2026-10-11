# Testing

## Testing Philosophy

Outside-In from the application layer. Integration tests implicitly cover internal components. Only add specific tests if there are edge cases NOT covered.

Approach:
1. Outside-in unit tests on the use cases (command/query handlers), with the ports replaced by fakes/mocks.
2. Entrypoint tests of the CLI commands, the tick and the event handlers.
3. Additional tests only for behavior NOT covered (filters, edge cases, transitions).

Adapter coverage:
- **Port adapters (repositories, agent runner, probes, state files):** contract tests with `@pytest.mark.integration`.
- **End-to-end tests:** happy path only, to check the full wiring DI → command → handler → port.

## Layout

- Tests mirror `src/`: `tests/grooveloop/{context}/{domain,application/commands,application/queries,infrastructure/...}/test_{module}.py`, plus `tests/grooveloop/cli/` and `tests/grooveloop/bootstrap/`. Tasks and services have no tests of their own: the tests of the command handlers that use them cover them.
- Shared fakes of the ports live in `tests/playground/shared/infrastructure/fake_{port}.py`; the same folder holds the test helpers several suites share (`clock_at(now)`, `github_client_for_any_repo()`, the GraphQL node builders of `github_slice_graph.py`).
- Mothers live in `tests/grooveloop/{context}/mothers/{entity}_mother.py`.
- `tests/conftest.py` holds the only global fixtures, all `autouse`: it restores the root bindings after each test, flushes the `GithubReadCache` and replaces the ports that would touch the real machine with their fakes (see `dependency-injection.md`).
- `tests/grooveloop/test_architecture.py` enforces the layer rules of `architecture.md`.

## Test Conventions

- All tests must be inside classes, never loose functions.
- `pyproject.toml` registers two markers and runs pytest with `--strict-markers`, so any other marker fails the run. Each test class carries the marker of what it starts from:
  - `@pytest.mark.entrypoint`: the class starts at an entrypoint (a CLI command's `run`, `main`, `tick.run`, an `EventHandler.handle`), with every external edge doubled (`Github` autospec, shared fakes from `conftest.py`). This includes the tick tests that run the real wiring against a doubled GitHub.
  - `@pytest.mark.integration`: the class exercises a real adapter against its edge (`tmp_path`, a real `git` repository, a subprocess, a doubled `Github` or GraphQL client). An end-to-end class of a CLI command that writes through a real adapter to `tmp_path` carries `integration` too (`TestNoteCommandEndToEnd`, `TestJournalCommandEndToEnd`).
  - Unit tests of handlers, detectors and the domain carry no marker.
- NO comments in tests under any circumstances.
- Domain unit tests cover: the **state machines of every aggregate** (`Slice`, `Lesson`, `SliceVerification`), the value objects with behavior or validation, the pure domain functions (`loop_signals`, `loop_activity`, `snapshot_slice_status`...) and the reusable parsers. The rest of the domain is covered through the handlers.
- The name of a shared setup helper describes all the state it builds, not the test case that introduced it.

## Property-based testing

**Rule:** Use property-based testing (Hypothesis) where it adds the most: the **transitions of the state machines** (`test_slice_lifecycle.py` checks every status × event against the transition table; `test_lesson.py` does the same for `Lesson`) and the `str → value | None` **parsers** (`parse_comment_directives`, `VerificationSection.parse`, the spec and agent profile parsers, the Claude session id and usage parsers). Do not force it where it adds nothing: the four states of `SliceVerification` are covered with explicit examples.

## The real agent CLI never runs in tests

**Rule:** The real `claude` or `opencode` binary **never** runs in tests: it requires the user's subscription and does not go in CI.

- Handler and entrypoint tests replace the agent ports with fakes (`FakeAgentRunner`, `FakeAgentRunnerRegistry`, `FakeAgentProfiles`).
- The `SubprocessAgentRunner` contract tests patch `Popen` in its module (`patch("grooveloop.shared.infrastructure.subprocess_agent_runner.Popen")`) and assert on the argv and the keyword arguments it would launch with. The `git fetch` and `git worktree add` run for real against a bare repository created in `tmp_path`. The `AgentCommand` is either a stub (`create_autospec(AgentCommand, ...)` with a fake argv) or the real `ClaudeCommand`, which only builds the argv.
- The tests of process handling (`test_run_process.py`, `test_signal_workspace_processes.py`) launch `/bin/sh` with `sleep`, never an agent.
- The `doctor` and `loop` tests override the engine probes with `PassingProbe`/`FailingProbe`, so they do not depend on the binaries being installed.

## Running Tests during TDD

**Rule:** During the TDD cycle, run only the test class being changed. Run the full suite (`make test`) only when finishing the slice or before creating the PR.

```bash
# ✅
uv run pytest tests/grooveloop/delivery/application/commands/test_mark_merged.py::TestMarkMergedCommandHandler
uv run pytest -m integration tests/grooveloop/delivery/infrastructure/test_github_slice_repository.py
```

## Mocks

- Use `create_autospec(X, spec_set=True, instance=True)`. Two documented exceptions:
  - A class whose instance attributes are set in `__init__` (`subprocess.Popen`, whose `pid` the test sets): `spec_set=True` would reject the attribute, so it is `create_autospec(subprocess.Popen, instance=True)`.
  - A port whose attributes are only annotated (`Probe.name: str`): the autospec does not see them. Use the shared fakes `PassingProbe` and `FailingProbe` (`fake_probe.py`) instead; a concrete probe class (`GithubPullRequestMergerProbe`) can still be autospecced.
- For asserts on dataclasses or values: `assert_called_with`, or read `call_args.args[0]` and assert on its fields. For entities/aggregates: get a direct reference.
- To replace a handler in an entrypoint test, use a fixture that opens `with container.override(XxxCommandHandler, mock):` and yields the mock. These fixtures live in the test module, never in a global `conftest.py`.
- To replace a function a CLI module calls (`tick.run` from `loop_command`, the command modules from `main`), use `patch.object(module, "name")`.
- In application layer unit tests, the ports are faked or mocked and passed in the constructor.

### Mock strategy and `mypy`

**Rule:** To avoid `mypy` errors with `create_autospec`: (1) The fixture returns `-> Any`, (2) The parameter in the test is typed as `Mock`.

```python
# ✅ tests/grooveloop/delivery/infrastructure/cli/test_usage_command.py
@pytest.fixture
def list_slice_sessions_handler() -> Any:
    mock = create_autospec(ListSliceSessionsQueryHandler, spec_set=True, instance=True)
    with container.override(ListSliceSessionsQueryHandler, mock):
        yield mock


@pytest.mark.entrypoint
class TestUsageCommand:
    def test_should_print_the_derived_cost_split_and_exit_zero(
        self, list_slice_sessions_handler: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ...
```

- `container.get(<ABC>)` does not need `# type: ignore[type-abstract]`: the `Container`'s `get` has an `Any` overload that accepts abstract interfaces without a mypy error.

## Fakes vs Mocks

- Use Fakes for ports with complex state: `FakeStoryRepository`, `FakeSliceRepository`, `FakeLessonRepository`, `FakeSliceVerificationRepository`, `FakeJournalEntryRepository` (in-memory aggregates), `FakeAgentRunner`, `FakeQueryBus` (answers per query type and records what was asked; an unexpected query fails the test).
- Use Mocks (`create_autospec`) for simple ports and dependencies without internal state (e.g. `Clock`, through `clock_at(now)`).
- Location of Fakes: `tests/playground/shared/infrastructure/fake_{component}.py`.

## Mother Pattern

**Rule:** Create a **domain** Mother when: constructor with 4+ parameters, entity used in 3+ tests, or complex setup with multiple optional fields. Location: `tests/grooveloop/{context}/mothers/{entity}_mother.py`. Today: `SliceMother`, `StoryMother`, `LessonMother`, `JournalEntryMother`. A Mother takes basic types and builds the aggregate with its constructor.

Abridged; the real `SliceMother.create` takes one parameter per constructor field:

```python
# ✅ tests/grooveloop/delivery/mothers/slice_mother.py
class SliceMother:
    @staticmethod
    def create(
        slice_id: str | None = None,
        status: SliceStatus = SliceStatus.PENDING,
        story_id: str | None = None,
        pull_request: PullRequest | None = None,
        review_verdict: ReviewVerdict = ReviewVerdict.EMPTY,
        depends_on: list[SliceId] | None = None,
    ) -> Slice:
        return Slice(
            id=SliceId(slice_id) if slice_id is not None else SliceId.generate(),
            status=status,
            story_id=StoryId(story_id) if story_id is not None else None,
            pull_request=pull_request,
            review_verdict=review_verdict,
            depends_on=depends_on,
        )
```

## Avoid Redundancy in Tests

Before adding a test, check whether the behavior is already covered by existing assertions. If it is already validated, SKIP the test. Only add tests that bring a different dimension of validation.

## Definition of Done per piece

**Rule:** When implementing a new piece, complete what applies:

- **Command or query handler:** (1) Command/Query + Handler in `application/commands/` or `application/queries/`, (2) unit tests with faked/mocked ports, (3) provider in `infrastructure/di.py` (and registration in the `QueryBus` if the query is asked through the bus), (4) an end-to-end test of the entrypoint, if the handler has one.
- **Detector:** the detector, its provider, its place in `DETECTORS` (`cli/tick.py`), and unit tests that give it the state through fakes of its ports and check the emitted `Event`s.
- **Event handler:** the handler, its entry in the module's `bind_event_handlers(...)`, and an `entrypoint` test that gives it the `Event` and checks the command it builds (with the command handler mocked).
- **Adapter or probe:** the adapter, its provider (and its place in `cli/preflight.py` for a probe), and `integration` contract tests against its edge.
- **CLI command:** the module with `run(...) -> int`, its subparser in `cli/main.py` with its exit codes in the epilog, and `entrypoint` tests that check the built command, the exit code and the output.

```python
# ✅ tests/grooveloop/slicing/application/commands/test_create_slices_from_spec.py
class TestCreateSlicesFromSpecCommandHandler:
    def test_should_materialize_one_slice_per_spec_item(self) -> None:
        repository = FakeStoryRepository()
        repository.save(StoryMother.create(story_id="story-1", slice_count=3))
        handler = CreateSlicesFromSpecCommandHandler(story_repository=repository)

        handler(CreateSlicesFromSpecCommand(story_id="story-1"))

        stored = repository.find(StoryId("story-1"))
        assert stored is not None
        assert len(stored.slices) == 3
```

There are no persisted events to check.

## Testing strategy

### Infrastructure

#### Entrypoints (CLI commands, the tick, event handlers)

**Rule:** CLI command tests replace the handler (with `container.override` in a fixture, not global), and validate the built `Command`/`Query`, the exit code, the output and the error mapping. The use case logic lives in the handler unit tests and in the adapter contract tests. Check both the exit code and the output (stdout or stderr, as `infrastructure.md` says).

```python
# ✅ tests/grooveloop/cli/test_doctor_command.py
def test_should_exit_nonzero_when_a_probe_fails(
    self, one_probe_fails: None, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = doctor_command.run()

    assert exit_code == 1
    assert "not available" in capsys.readouterr().out
```

The end-to-end test (happy path) checks the full wiring command → handler → domain → ports, cutting only at the external edges (GitHub, the agent subprocess, the filesystem under `tmp_path`).

#### `watch`

The `watch` tests build `LoopsApp` from the real container and drive it with `App.run_test()` and its `Pilot`, pressing keys and querying widgets. They use a long refresh interval and trigger the refresh by hand, so a test never waits for the timer.

### Application

- Command handlers: receive an `XxxCommand` (frozen dataclass with basic types) and return the declared result (`None` today). Query handlers: receive an `XxxQuery` and return its `XxxQueryResult` (`| None` only where the absence is a real outcome). Introduce only the ports needed (faked/mocked).

### Domain

- Domain objects in test data setup are instantiated with the constructor, unless a Mother pattern is defined. Do not use factory methods.
- The `Slice` and `Lesson` state machines are tested with property-based testing.

### Infrastructure (outbound ports)

#### Adapter Tests (`GithubStoryRepository`, `GithubSliceRepository`, `SubprocessAgentRunner`, the `Filesystem*` and `Local*` adapters, the probes)

**Rule:** Contract tests that exercise the real adapter against its external edge (or a double of the edge), never through another adapter of the same port. The real agent CLI never runs (see above).

- Do not include suffixes such as `_with_real_adapter` or `_end_to_end` in integration test names. The `@pytest.mark.integration` marker already says so.
- If a slice implements infrastructure without an entrypoint (e.g. adapter + DI), do NOT write an end-to-end integration test. The full test is written in the slice that implements the entrypoint.

## Anti-patterns

- ❌ Tests as loose functions outside classes.
- ❌ Comments in tests.
- ❌ A marker other than `integration` or `entrypoint` — `--strict-markers` rejects it.
- ❌ Mocking value objects — use real instances.
- ❌ Redundant tests that check behavior already covered.
- ❌ Creating the test state with the same adapter being tested — seed the external edge directly.
- ❌ Global mock fixtures shared between modules.
- ❌ Running the real agent binary in tests — fake the `AgentRunner` port, or patch `Popen` in the runner's tests.
- ❌ `create_autospec(X)` without `spec_set=True, instance=True` outside the two documented exceptions.
- ❌ A setup helper used by several tests whose name describes only one of the cases it builds — name it after the full state.

# Infrastructure Layer

The infrastructure holds the **entrypoints** (CLI commands, detectors, event handlers) and the **adapters** that implement the domain ports. See ports in [ADR-0004](../adr/0004-ports-and-adapters.md).

## Entrypoints: CLI commands

`cli/main.py` parses the arguments with `argparse` and calls the `run(...)` function of each command module. A command that belongs to one context lives in `{context}/infrastructure/cli/` (`usage_command.py`, `note_command.py`, `journal_command.py`). The commands that coordinate several contexts live in the top-level `cli/`, the **composition root**, which belongs to no bounded context (see [ADR-0005](../adr/0005-context-map.md)): `loop_command.py` and the `tick.py` it drives, `watch_command.py` with the Textual app (`watch_app.py` and its panels), `doctor_command.py`, the shared `preflight.py` and `invocation_inputs.py`.

- All real dependencies are obtained with `container.get(...)` directly inside the function that handles the command. There is no custom `__init__` to inject use cases.
- The command gets the `CommandHandler`/`QueryHandler` with `container.get(...)` and invokes it with `handler(command)` / `handler(query)`.
- The CLI input values that adapters and event handlers need (`TargetRepo`, `AgentWorkdir`, `VerifyDeploy`, `MaxReviewRounds`, `MaxParallelSlices`, `JournalEnabled`, `MaxRetries`, `AutoMerge`) are `frozen` value objects bound once with `bind_invocation_inputs(...)` (see `dependency-injection.md`).
- Values the module passes around internally are `frozen` dataclasses defined in the same module (`_TickInputs`, `_TickResult` in `loop_command.py`), or the `frozen` DTOs of a `QueryResult` when the output is exactly that DTO.
- **Exit codes** come from `ExitCode` (`shared/infrastructure/cli/exit_code.py`), shared by every command: `0` ok, `1` the command ran and the result is a failure, `2` usage error, `3` preflight failed, `4` missing context. Each subparser lists the codes it uses in its `--help` epilog with `describe_exit_codes(...)`.
- Diagnostics (`[warn]`, `[fail]`, usage errors) go to **stderr**; the normal output, including `[ok]` lines, goes to stdout. `doctor` is the exception: its report, `[fail]` lines included, is its output and goes to stdout.
- `main` configures `logging` once, before parsing the arguments: one stderr handler on the `grooveloop` logger with the format `%(asctime)s %(levelname)s %(message)s` and the level of `GROOVELOOP_LOG_LEVEL` (default `WARNING`, an unknown value means `WARNING`). The logs of other libraries keep the `logging` defaults.
- **Run ids** are `uuid4` strings (`SubprocessAgentRunner.dispatch`); the short id is their first 8 characters.

### Command surface

| Command | Purpose |
|---|---|
| `doctor` | Run the preflight (`cli/preflight.py`) and print one `[ok]`, `[warn]` or `[fail]` line per probe. Exits `1` if a required probe fails. `--workdir` chooses the checkout the agent profiles are read from; `--repo` adds the merger probe of that repository. |
| `loop` | Run the same preflight, refuse to start with exit `3` if a required probe fails, make sure the state and verdict labels exist (`GithubDeliveryLabels.ensure()`), and then drive the repo as a headless daemon: one tick every `--tick-interval` seconds (or a single one with `--once`). After each tick it publishes `snapshot.json`, the `pulls/<n>.json` of the open PRs and the `stories/<n>/spec.md` files for `watch`. The heartbeat is written by its own daemon thread every `--interval` seconds, even while a tick takes long. In continuous mode a failed tick writes `[fail]` to stderr and the loop goes on; Ctrl-C exits `0`. |
| `watch` | Textual app (`LoopsApp`) that shows every live loop of the machine from its state files, without touching GitHub. Each refresh reads the loops with `ListLoopsQuery` in a thread worker and skips a refresh while the previous read is still running. A loop list on the left, the chosen Story in the center (a `StorySelector` with one option per Story and its signal, `[`/`]` to change it, and a `TabbedContent` with **Slices**, **Spec** and **Journal**) and a detail panel on the right (`PullRequestPanel` for a slice or a lesson, `RunPanel` for a run). `Enter` maximizes the detail, `Esc` restores the columns, `o` opens the focused PR or Issue, `f` filters the journal, `q` quits. Without a TTY it exits `2`; `--screenshot <file>.svg` paints one frame of a fixed 160×48 screen without a terminal, saves it and exits `0`. |
| `usage` | Show the cost of each session of a slice split per token class and per model (`ListSliceSessionsQuery`). Exits `1` if the slice has no sessions. |
| `note` | Append an entry to a Story's journal. Inside an agent run, repo and Story come from the `run.json` named by `GROOVELOOP_RUN_ID`; outside one, without `--repo` and `--story`, it exits `4`. |
| `journal` | Show a Story's journal, with the same context rules as `note`. |

### The tick

`tick.run(...)` is the composition root of one pass (see [ADR-0006](../adr/0006-events-without-broker-detected-by-polling.md)). It runs the **detectors** and hands each event to the `EventDispatcher`. It does not persist events or decide anything ad hoc. Its steps, in order:

1. `bind_invocation_inputs(...)` binds the CLI inputs in the root injector.
2. **Close abandoned runs**: `AgentRunAbandonedDetector` emits `AgentRunAbandoned` for each run of the repo that vanished or stalled, and `CloseAgentRunWhenAgentRunAbandoned` invokes `CloseAgentRunCommandHandler`, which closes its `agent.log`. It runs before the other detectors, so they all read a closed run as finished.
3. **Drive the domain**: flush `GithubReadCache`, then run every detector of `DETECTORS` in its listed order and dispatch each event. With `--story`, events of other Stories are skipped. An event that dispatches an agent (`SliceReadyToDispatch`, `ImplementationInterrupted`, `PullRequestApproved`...) that fails only writes `[warn] dispatch failed for slice <n>`; any other failure aborts this step.
4. **Sweep workspaces**: `AgentWorkspaceAbandonedDetector` emits `AgentWorkspaceAbandoned` for up to 20 finished runs, and `RemoveAgentWorkspaceWhenAgentWorkspaceAbandoned` invokes `RemoveAgentWorkspaceCommandHandler`. It runs even if step 3 failed.
5. Print `[ok]   ran tick in <repo>` and return `0`, or `[fail] run tick in <repo>: <error>` and return `1`.

Steps 2 and 4 never fail the tick: a failure writes a `[warn]` line and the tick goes on.

```python
# ✅ cli/tick.py (abridged)
DETECTORS: list[type[_Detector]] = [
    StoryReadyToSliceDetector,
    PullRequestOpenedDetector,
    ReviewOutcomeDetector,
    ...
    StoryCompletedDetector,
    LessonCapturedDetector,
    RefinementOutcomeDetector,
    LessonResolvedDetector,
]


def _drive_domain(repo_full_name: str, story: int | None) -> None:
    container.get(GithubReadCache).flush()

    dispatcher = container.get(EventDispatcher)
    scope = _story_scope(story)

    for detector_type in DETECTORS:
        for event in container.get(detector_type).detect():
            if scope is not None and not _within_scope(event, scope):
                continue

            if isinstance(event, _DispatchingEvent):
                _dispatch_slice(dispatcher, event, repo_full_name)
                continue

            dispatcher.dispatch(event)
```

The order of `DETECTORS` matters: a detector sees the state the previous ones left. `StoryCompletedDetector` closes the Story Issue, which removes its sub-issues from the graph, so the detectors that read sub-issues come before it.

## Preflight

**Rule:** Every external dependency the loop needs has a probe: a class that inherits from `Probe` (`shared/application/probes/probe.py`), declares a `name` and implements `check()`, which proves empirically that the dependency can honor its contract and raises with the reason when it cannot. Probes are wired like any other dependency and obtained with `container.get(...)`. Adapters do not carry a `probe()` method. Startup invariant: `wire → probe → use`.

`cli/preflight.py` is the only place that decides which probes run, and `doctor` and `loop` use the same `run_preflight(with_merger=...)`:

- **Required:** `GithubAuthProbe`, `GithubGraphQLProbe`, `GrooveloopCliProbe`, `AgentProfilesProbe`, and the engine probes (`ClaudeProbe`, `OpencodeProbe`) **only for the engines that the agent profiles use**. With `loop --auto-merge` or `doctor --repo`, also `GithubPullRequestMergerProbe`.
- **Optional:** `DockerComposeProbe`. Docker is optional: the probe passes without `docker`, and if `docker` is there without the `compose` plugin, the failure is reported as `[warn]` and does not fail the preflight.
- A probe that cannot even be built (`container.get` raises) counts as a failure of that probe.

## Detectors

**Rule:** A **detector** reads and synthesizes the `Event`s of the tick's actionable conditions (see [ADR-0006](../adr/0006-events-without-broker-detected-by-polling.md)). It **only reads**: through the context's repository or its other ports (`AgentRunner.outcome_of`/`verdict_of`, `QueryBus`, `AbandonedAgentRuns`, `AgentWorkspaces`, `LearnSignal`...). It never writes GitHub, never writes a file and never signals a process. It only emits events whose predicate holds now; when the command handles them, the state changes and the detector stops emitting them.

- File in `{context}/infrastructure/detectors/{event}_detector.py`, named after the event it emits (`PullRequestMergedDetector` emits `PullRequestMerged`).
- A detector that emits mutually exclusive outcomes of one read is named after the condition: `{condition}_outcome_detector.py` (`ReviewOutcomeDetector` emits `ReviewCompleted`, `HumanDecisionRequired` or `BlockingReviewDetected`; `RefinementOutcomeDetector` emits `LessonLearned` or `LessonDiscarded`).
- The decision lives in the aggregate's guards; the detector filters with `search()` criteria and asks the aggregate.

```python
# ✅ delivery/infrastructure/detectors/pull_request_merged_detector.py
class PullRequestMergedDetector:
    def __init__(self, slice_repository: SliceRepository) -> None:
        self._slice_repository = slice_repository

    def detect(self) -> Iterator[PullRequestMerged]:
        for a_slice in self._slice_repository.search():
            if not a_slice.can_be_merged():
                continue

            pull_request = a_slice.pull_request
            if pull_request is not None and pull_request.is_merged():
                yield PullRequestMerged(slice_id=a_slice.id)
```

The search has no `status` or `open` criterion on purpose: a merge can happen in any in-progress state, and the `Closes #N` of the PR has already closed the sub-issue.

## Event Handlers

**Rule:** To react to an `Event`, file in `{context}/infrastructure/event_handlers/{command}_when_{event}.py`. It inherits from the `EventHandler` base, declares the `event_class` it listens to and in `handle(event)` gets the command handler with `container.get(...)`, builds the command with basic types (reading the CLI inputs it needs from the container) and invokes it. It is registered in the `EventDispatcher` from the context's DI (see `dependency-injection.md`).

```python
# ✅ delivery/infrastructure/event_handlers/mark_merged_when_pull_request_merged.py
class MarkMergedWhenPullRequestMerged(EventHandler[PullRequestMerged]):
    event_class = PullRequestMerged

    def handle(self, event: PullRequestMerged) -> None:
        handler = container.get(MarkMergedCommandHandler)

        handler(MarkMergedCommand(slice_id=event.slice_id.value))
```

The handler receives an `Event` (typed in-memory object, **not** a broker payload) and the command it invokes is **idempotent**: if the condition is detected again before the state changes, rerunning the command causes no harm (see `application.md`).

## Adapters

Adapters implement the domain ports. The file name carries the prefix of the implementation (see `architecture.md`): `github_`, `claude_`, `opencode_`, `subprocess_`, `local_`, `filesystem_`, `docker_`, `signal_`, `system_`, `injector_`, `mapped_`, `cached_`.

### GitHub repositories

One adapter per aggregate repository (ADR-0004), mapping the domain to GitHub primitives. They are the domain source of truth (ADR-0003):

- `GithubStoryRepository` implements `StoryRepository`: Story → parent Issue with the `grooveloop` label; the `Spec` is parsed from the Issue body (`spec_markdown_parser.py`); the life cycle is the `ready_for_implementation`/`sliced`/`done` labels.
- `GithubSliceRepository` implements `SliceRepository`: Slice → sub-issue; state, run, PR, rounds, verdict, retries and failure cause → labels (`pr_open`, `run:<id>`, `pr:N`, `review-round:N`, `review:<verdict>`, `retry:N`, `failure:<cause>`); the `PullRequest` and its comments → the PR linked to the sub-issue.
- `GithubSliceVerificationRepository` and `GithubLessonRepository` follow the same idea with the `verification:*`/`verif-retry:N` labels of the sub-issue and with one Issue per lesson.
- They read the Story graph through `GithubStoryGraph` (GraphQL) and cache reads in `GithubReadCache`, which the tick flushes at its start.

```python
# ✅ delivery/infrastructure/github_slice_repository.py
def search(
    self, story_id: StoryId | None = None, status: SliceStatus | None = None, open: bool | None = None
) -> list[Slice]:
    nodes = self._slice_nodes(story_id, open)
    matching = [node for node in nodes if status is None or self._status_from(node) == status]
    matching.sort(key=order_of)

    return [self._to_slice(node) for node in matching]
```

**Rule:** The mapping method (`_to_slice`, `_to_story`, `_to_lesson`, `_to_verification`) fails loudly with `raise` when the external edge lacks a value that an invariant of the adapter itself guarantees (a label that `save` always writes and no human edits), instead of returning a silent default that masks a corrupt source: `GithubLessonRepository` raises when a lesson lacks its `source_pr:` or `learning:` label. A label that humans write or relabel by hand maps its absence to a domain state instead: a sub-issue without a state label reads as `PENDING` (pausing and retrying a slice are manual relabels), a Story without a life-cycle label reads as `DRAFT`, and a sub-issue without a `verification:` label reads as `VerificationStatus.EMPTY`.

### `SubprocessAgentRunner` (detached subprocess)

It implements `AgentRunner` by launching the agent engine as a **detached subprocess** that survives the parent's death. The engine argv does not live in the runner: it is provided by an `AgentCommand` (`ClaudeCommand`, `OpencodeCommand`), which also declares its `engine` for `run.json`. `MappedAgentRunnerRegistry` holds one runner per engine and the dispatching handlers ask it with the `engine` of the `AgentProfile` (`runner_for(profile.engine)`). Launch idiom:

- The argv runs inside `/bin/sh -c '<argv> "$1"; printf "\n[AGENT_EXIT] %s\n" "$?"'`, with the run-dir as `$0` and the instruction as `$1`; the `[AGENT_EXIT] <code>` line at the end of `agent.log` is how the loop knows the run ended.
- `start_new_session=True` (session leader, detached from the terminal).
- Log fds opened with `O_APPEND` and an explicit `os.fchmod(fd, 0o644)` (the mode of `os.open(..., 0o644)` is masked by the umask).
- `stdin=subprocess.DEVNULL` (do not inherit or block the terminal's stdin).
- `close_fds=True`; the parent closes **its** copies of the fds after launching.
- `GROOVELOOP_RUN_ID=<run id>` is added to the environment, so `grooveloop note` inside the run finds its `run.json`.
- **Post-hoc classification**: `outcome_of`/`verdict_of` read the run from its files, never from a live stream. No exit marker is `RUNNING`; `[AGENT_EXIT] 0` is `SUCCEEDED`; a non-zero code is `INTERRUPTED` (cause `stalled` or `vanished` if the loop closed it, see below) or whatever the `AgentLogReader` of the run's engine reads from the tail of the log (`ClaudeLogReader`, `OpencodeLogReader`). Both methods only read.

Gotchas:

- The child is reparented to init/launchd, which reaps it: **fire-and-forget with no reaper thread**. No `Popen.wait()`.
- **Buffering to file**: the binary, when writing to a file (not a tty), may be block-buffered; validate it against the real binary if line-by-line streaming is needed.
- The `pid` of the launched `sh` is stored in `run.json`, and the run-dir path in its command line.
- **Abandoned runs** are closed by the tick, not by the reader (`LocalAbandonedAgentRuns`, behind `AbandonedAgentRuns`). A run with a `pid` and an `agent.log` without `[AGENT_EXIT]` is abandoned when its process vanished (the pid no longer exists, or its command line, `ps -ww -o command=`, does not contain the run-dir) or when it stalled (its `agent.log` has not been written for 30 min, mtime against the `Clock`). `close(run_id)` appends `[AGENT_VANISHED]` and `[AGENT_EXIT] 143` to a vanished run; to a stalled one it first sends `SIGTERM` to the process group and `SIGKILL` if the group is still alive 10 s later, and then appends `[AGENT_STALLED]` and `[AGENT_EXIT] 143`. On macOS `os.killpg` does not always deliver the signal to the group leader, so each signal goes first to the leader with `os.kill` and then to the group; and `killpg(pgid, 0)` gives `EPERM` as soon as the group has a zombie, so the group's liveness is checked with `ps -A -o pgid=,stat=` discarding processes in state `Z`. A run without a `pid` stays `RUNNING` until its marker.
- `resume(previous_run_id, instruction)` relaunches the previous run's session without creating a worktree: the argv comes from `AgentCommand.resume_argv(model, log_head)` (`ClaudeCommand` adds `--resume <session_id>` read from the head of `agent.log`; `OpencodeCommand` returns `None`). The new run runs in the previous one's worktree and its `run.json` copies the previous one's metadata with `resumed_from` and `workdir`. It returns `None` without `run.json`, without a worktree, without a `session_id` or with another engine; the caller dispatches again. `pushed_branch_of` and a chained resume read the worktree from the `workdir` key if it exists.
- The worktree of a new run is `<run>/s<slice>-<run8>` (the slice id and the first 8 characters of the run id), detached at `origin/master` after a `git fetch origin master` of `--workdir`: target repos that derive the Docker project name from the folder do not share a project between runs. If the dispatch fails, that worktree and the run-dir are deleted and a failed `git` call raises `GitCommandError` with the tail of its stderr. Every run's `run.json` declares in `workdir` the absolute path of its worktree. The sweep (`LocalAgentWorkspaces`) uses that key: a worktree declared by an unfinished run or within the 30 min grace period after its end is not deleted, a worktree declared by several runs is listed only once, with the lowest of its ids in alphabetical order (not the oldest run), and `remove` deletes the declared worktree (`git worktree remove --force` and `prune`). Without the key (old runs) the worktree is `<run>/workdir`; a declared path that is not strictly inside a run-dir (outside the runs directory, the runs directory itself or a whole run-dir) is ignored.
- Before deleting the worktree, `RemoveAgentWorkspaceCommandHandler` asks `AgentWorkspaces.workspace_of` for its path (it never reads it on its own) and cleans up what was born in it, in this order: first it terminates the processes with the `WorkspaceProcesses` port (`SignalWorkspaceProcesses`), because they can start containers again: `SIGTERM` to each process whose working directory is inside the worktree and `SIGKILL` to those still inside 5 s later. The working directory is read from `/proc/<pid>/cwd` on Linux and from `lsof -d cwd` on macOS, and the loop itself is never signaled. Then it brings down what is left with the `WorkspaceContainers` port (`DockerWorkspaceContainers`): `docker compose -p <project> down -v --remove-orphans` for each Compose project whose `com.docker.compose.project.working_dir` is inside the worktree, and `docker rm -f -v` of the non-Compose containers that mount a worktree path. Containers are read with `docker ps -aq` + `docker inspect`, and the commands run from an empty temporary directory so that Compose does not load an unrelated file. Without `docker` installed, or with the daemon not responding, the step does nothing. If a step fails, the next ones run anyway, the worktree is deleted and the handler re-raises the first failure, which the tick writes as `[warn] sweep failed for run <run>`.
- Secrets (tokens) only in memory or in environment variables, **never on disk or in a log**. The GitHub token is read from `gh auth token` once per process, when the singleton `Github` client is built.

### Instrumentation and state files

Instrumentation (ADR-0003) is what the commands print and the files the loop writes under `~/.grooveloop/`. None of it is domain state, and none of it is an outbox of events: `Event`s are not persisted (see [ADR-0006](../adr/0006-events-without-broker-detected-by-polling.md)).

- **Lines:** `[ok]`, `[warn]` and `[fail]` lines with the repo and the subject (`[warn] dispatch failed for slice 12 in owner/repo: ...`). `doctor` and the preflight print one per probe.
- **Handler logs:** the `INFO` records of the `CommandHandler`/`QueryHandler` base classes (see `application.md`) reach stderr only with `GROOVELOOP_LOG_LEVEL=INFO` (or `DEBUG`); the default `WARNING` drops them.
- **Run-dirs** (`RunsDir`, written by `SubprocessAgentRunner`, read by `LocalAgentSessionRepository`, `FilesystemAgentRunLogs`, `LocalAbandonedAgentRuns`, `LocalAgentWorkspaces`...):

```
~/.grooveloop/runs/{run-id}/run.json        # task_type, started_at, slice_id, repo, story_id, profile, engine, launch_model, workdir, pid (+ resumed_from)
~/.grooveloop/runs/{run-id}/agent.log       # stdout of the agent, ending with [AGENT_EXIT] <code>
~/.grooveloop/runs/{run-id}/agent.err       # stderr of the agent
~/.grooveloop/runs/{run-id}/usage.json      # usage memoized by LocalAgentSessionRepository once the run is terminal
~/.grooveloop/runs/{run-id}/turns.json      # turn growth memoized by LocalAgentSessionRepository
~/.grooveloop/runs/{run-id}/s{slice}-{run8}/  # worktree where the agent runs (old runs: workdir/)
```

- **Per-repo state files** (`ReposDir`), written atomically (temporary file + `os.replace`) for `watch` (ADR-0007, ADR-0008):

```
~/.grooveloop/repos/{owner}/{repo}/heartbeat.json                    # presence of that repo's loop (FilesystemLoopPresence)
~/.grooveloop/repos/{owner}/{repo}/snapshot.json                     # Stories, slices, lessons, PR summaries and the last tick (FilesystemLoopSnapshots)
~/.grooveloop/repos/{owner}/{repo}/pulls/{n}.json                    # detail of each open PR of a slice or of a lesson (FilesystemPullRequestDetails)
~/.grooveloop/repos/{owner}/{repo}/stories/{n}/spec.md               # body of each Story, rewritten only when it changes (FilesystemStorySpecs)
~/.grooveloop/repos/{owner}/{repo}/stories/{n}/journal/{at}-{author}.json  # one journal entry (FilesystemJournalEntryRepository)
```

The journal is the only file under `~/.grooveloop/` that is domain state: `JournalEntry` is an aggregate whose repository is the filesystem. Each file stores the entry's `id` with its `kind`, `author`, `body`, `story_id` and `written_at`, so an entry keeps its identity across reads; an entry written before the `id` was stored is read with a deterministic id, a `uuid5` of its path under `ReposDir`, never a random one.

## Anti-patterns

- ❌ Injecting dependencies in the entrypoint constructor — get them with `container.get(...)` inside the function.
- ❌ An exit code written as a bare integer — use `ExitCode`.
- ❌ A diagnostic on stdout, or a normal output on stderr (except the `doctor` report).
- ❌ Parsing the agent stream live instead of post-hoc classification over the log.
- ❌ Launching the agent subprocess without `stdin=DEVNULL` or without `start_new_session=True`.
- ❌ Relying on the umask for the log permissions — use an explicit `os.fchmod`.
- ❌ Secrets on disk or in a log.
- ❌ A `probe()` method on an adapter, or a command that picks its own probes — add a `Probe` class and list it in `cli/preflight.py`.
- ❌ Using an external dependency the preflight does not probe — it breaks the `wire → probe → use` invariant.
- ❌ Publishing events when a command finishes or emitting them from the aggregate — events are synthesized by the detectors (ADR-0006).
- ❌ Persisting events (outbox, queue, table) or marking events as "processed" — idempotency and state guards are enough.
- ❌ A detector that mutates state (GitHub, a file, a process) — it only reads and emits events; closing runs and sweeping worktrees are commands of their own.
- ❌ A non-idempotent command behind an event handler — an event can be detected again before the state changes.
- ❌ A mapping method that returns a silent default for a missing value guaranteed by an invariant — `raise` so as not to mask a corrupt source.

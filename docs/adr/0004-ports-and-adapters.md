# ADR-0004: Ports and adapters of the orchestrator

## Status

Accepted — 2026-06-22

## Context

The orchestrator depends on two external systems that must be able to change without touching the core: **where the SDLC state lives** (GitHub today) and **who runs the agents' work** (Claude Code today). It also needs a controllable notion of time for the domain and the tests.

The carryover (§11) validated empirically how to invoke Claude Code as a *detached* subprocess that survives the parent, and (§12) recommends a pure core with a contractual `probe()` per external dependency.

## Decision

> **Update (2026-10):** The table below lists the first ports. Today every aggregate of each context has its repository (`SliceVerificationRepository`, `LessonRepository`, `JournalEntryRepository` besides these two) and `shared` adds `AgentCommand`, `AgentLogReader`, `AgentRunnerRegistry`, `AgentProfiles` and the ports of the run-dirs and state files; see [`architecture.md`](../conventions/architecture.md). Probes are `Probe` classes with a `check()` method, not a `probe()` method on each adapter, and `cli/preflight.py` runs the same set for `doctor` and before `loop` starts: the engine probes only for the engines the profiles use, `DockerComposeProbe` as an optional `[warn]`, and `GithubPullRequestMergerProbe` with `--auto-merge` or `doctor --repo`. There are no `[PHASE_START]`/`[PHASE_END]` markers: a run is classified from the `[AGENT_EXIT] <code>` line that the runner's shell wrapper appends to `agent.log`, and from the engine's `AgentLogReader`. `ClaudeCommand` runs `claude --print --output-format stream-json --verbose --strict-mcp-config --model <model> --settings <json>`, and there are four packaged profiles (`developer`, `reviewer`, `scribe`, `verifier`). See [`infrastructure.md`](../conventions/infrastructure.md).

The domain ports are defined **one per aggregate** (plus the service ports), each in its own file, with interchangeable adapters. There is no "god" repository spanning several aggregates.

| Port | Responsibility | v1 adapter | Future |
|---|---|---|---|
| `StoryRepository` | Read/save the Story (parent Issue) and its `Spec` (value object); search Stories by state | `GithubStoryRepository` | sqlite, postgres |
| `SliceRepository` | Read/save the `Slice` aggregate (sub-issue + state + its `PullRequest` and comments); search slices by Story/state | `GithubSliceRepository` | sqlite, postgres |
| `AgentRunner` | Dispatch the planning+implementation agent of a slice; improve a PR according to comments | `SubprocessAgentRunner` (+ `ClaudeCommand`, `OpencodeCommand`), resolved per engine with `AgentRunnerRegistry` | codex, direct LLM-API |
| `Clock` | Provide "now" to the domain | system adapter | fake in tests |

The `PullRequest` (with its review comments) is an **internal entity of the `Slice` aggregate**, not an independent aggregate: it has no repository of its own. The `Spec` is a **value object of the `Story` aggregate**.

**`SubprocessAgentRunner` runs via a detached subprocess** (idiom validated in carryover §11), taking the engine argv from an injected `AgentCommand` (`ClaudeCommand` builds `claude --print --output-format json --model <model>`): `start_new_session=True`, log fds with `O_APPEND` and an explicit `os.fchmod`, `stdin=DEVNULL`, `close_fds=True`. The run's phase classification is **post-hoc** (the log is replayed after it finishes), relying on `[PHASE_START]/[PHASE_END]` markers emitted by the agent prompt.

**Engine selection per profile:** the `AgentProfile` declares its `engine` and the `dispatch` call sites ask the `AgentRunnerRegistry` port for the runner (`MappedAgentRunnerRegistry` maps `engine → AgentRunner`). Each engine provides its `AgentCommand` —`ClaudeCommand` and `OpencodeCommand` (`opencode run --format json -m <model> --dangerously-skip-permissions`)— and shares the same detached idiom, the same worktree and the same `run.json`. An unregistered `engine` raises `UnsupportedEngineError`. The default engine of the three packaged profiles is still `claude`; the switch is the target repo's `.grooveloop/agents/<profile>.md` override, and the runtime rollback is deleting it.

**Reading usage per engine:** a run's usage is not produced by the runner, it is translated by the reader. `LocalAgentSessionRepository` resolves an `AgentLogReader` with the `engine` it reads from `run.json` and gets an `AgentRunReading`: `ClaudeLogReader` parses the `result` event from the tail of `agent.log`; `OpencodeLogReader` takes the first `sessionID` from the NDJSON of events and invokes `opencode export <sessionID>`, aggregating per model the `cost` and the `tokens {input, output, cache{read,write}}` of each `assistant` message (`reasoning` is discarded). Since `export` is a subprocess and the panel refreshes in a loop, the normalized usage is memoized in `usage.json` in the run-dir the first time the reader sees the run terminal with usage. An engine without a reader, or an `export` that fails, leave the run **without metrics** instead of breaking the panel. The heartbeat of a live run does not go through the reader: it is the mtime of `agent.log`, engine-agnostic, and the panel marks with `⚠ stalled` the run that has gone more than `--stall-after` seconds without writing.

Two empirical findings against opencode 1.15.5 correct what the Spec anticipated:

- The model identity does **not** live in an `info.model {providerID, id}`: each `assistant` message carries **flat** `providerID` and `modelID`, and the session `info` brings the totals but no model. Hence the aggregation per message (the sum matches the session's `info.tokens`/`info.cost`).
- `opencode export` **truncates its output to ~64 KB when stdout is a pipe** (5.9 MB with stdout to a file for the same session). The export is therefore captured by redirecting stdout to a temporary file, not with `capture_output`.

**Mandatory `probe()`/preflight:** each adapter implements `probe()`, which proves empirically that it can honor its contract in the real environment (GitHub auth, `claude` and `opencode` binaries available, profiles with an `engine` from `SUPPORTED_ENGINES`). Startup invariant: `wire() → probe() all → use()`. If a `probe()` fails, the CLI refuses to start with exit code != 0 (the `doctor` command materializes it).

## Consequences

- The domain and the application depend only on the ports; the adapters live in `infrastructure/`.
- Migrating persistence or the agent engine means writing a new adapter and changing the DI provider.
- The preflight catches most setup failures before spending work.
- In tests, the real `claude` CLI never runs; `AgentRunner` is replaced by a fake (see the testing conventions).

## Alternatives considered

- **Calling the LLM API directly in v1:** discarded; Claude Code as a subprocess reuses the user's environment and the already validated idiom, and it stays behind the port for future engines.
- **An `OpencodeAgentRunner` sibling of Claude's:** discarded; it would duplicate the worktree, the fds and the metadata for each engine. The variation between engines is only the argv, so it lives in the `AgentCommand` and the runner is unique.
- **Coupling the state to GitHub without a port:** discarded; it would break the evolvability to sqlite/postgres that motivates the architecture (see [ADR-0003](0003-hybrid-state-and-log-instrumentation.md)).

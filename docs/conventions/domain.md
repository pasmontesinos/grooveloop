# Domain Conventions

## Entities and Aggregates

- They are not dataclasses. No *Entity* or *Aggregate* suffix.
- Identifiers are Value Objects named `{Entity}Id` (e.g. `SliceId`, `StoryId`, `LessonId`) that inherit from `shared/domain/identifier.py`'s `Identifier`, a `frozen` dataclass with a single `value: str`. An identity that GitHub assigns (an issue number) is built with the constructor (`SliceId("12")`); an identity the domain generates comes from `Identifier.generate()`, a `uuid4` (`JournalEntryId.generate()`).
- All attributes are private (`_` prefix). Use `@property` to expose attributes.
- The constructor (`__init__`) takes every attribute; the repositories rehydrate with it. Creating a new instance goes through a named factory `@classmethod` that returns `Self` and sets the initial state: `Lesson.create(...)`, `JournalEntry.write(...)`, `Slice.create(...)` in `slicing`, `PullRequest.anchor(number)`. An aggregate that the loop never creates (the `Story`, the `delivery` `Slice` and the `SliceVerification`, which are Issues that already exist) has no factory.
- Defined in their own module.

Aggregates (one repository per aggregate, see "Ports"; each one lives in its context, see [ADR-0005](../adr/0005-context-map.md)):

- **Story** (`slicing`) — the parent Issue. It holds the **`Spec`** of the change (value object with its slices, order and dependencies already parsed). `Story.materialize_slices(verify_deploy)` turns the Spec into the `slicing` `Slice`s that become sub-issues; `Story.complete()` closes it.
- **Slice** (`delivery`) — the work item of each sub-issue. It carries its dependencies and, **once its PR is anchored, its `PullRequest`** (with the review comments) **inside the aggregate itself**. It moves through the state machine below.
- **SliceVerification** (`verification`) — the verification of a merged slice: `EMPTY → RUNNING → CONCLUDED`, or `RUNNING → FAILED`.
- **Lesson** (`learning`) — the lesson captured from the `/grooveloop-learn` comments of a merged PR: `IN_PROGRESS → LEARNED | DISCARDED`, then closed.
- **JournalEntry** (`journal`) — an entry of the Story journal. It has no life cycle.

The "Slice" concept is modeled differently in each context: in `slicing` it is an item of the Spec with its order and dependencies by position; in `delivery` it is the work item with a life cycle; in `verification` it is the verification of a merged one. Each context declares its own `SliceId`; they share the value (the sub-issue number), not the class.

The `PullRequest` **is not an independent aggregate**: it is an internal entity of the `Slice` aggregate. It has no repository of its own.

## Value Objects

- Immutable dataclasses (`frozen`). No *VO* or *ValueObject* suffix.
- Defined in their own module.
- Examples: `StoryId`, `SliceId`, `SliceOrder`, `PullRequestNumber`, `Spec` (inside the `Story` aggregate), `ParallelSliceLimit`, `RetryPolicy`, `AgentRunVerdict`.

## Enums

There are two variants depending on whether the enum models the domain's "absent" state or not:

### Variant A — Enums without an "absent" state

- Define as `StrEnum` with an uppercase name and a lowercase value (e.g. `SliceStatus.MERGED = "merged"`).
- The aggregate declares the field with the enum type directly (never `Optional[Enum]`).

```python
# ✅ delivery/domain/slice_status.py
from enum import StrEnum


class SliceStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    UNDER_REVIEW = "under_review"
    PR_OPEN = "pr_open"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"
    MERGED = "merged"
    FAILED = "failed"
```

### Variant B — Enums with an "absent" state

- Define as a plain `Enum` (not `StrEnum`) with an `EMPTY = None` member besides the lowercase string members. Today: `ReviewVerdict`, `AgentRunCause` and `VerificationStatus`.
- `EMPTY` represents absence at the external edge (no label, `null` in a file). The aggregate declares the field as the enum type, **not** as `Optional[Enum]`.
- Reading the edge uses `Enum(value)`, which resolves `None → EMPTY` without a branch. Writing uses `member.value`; a label cannot be absent and present at once, so the adapter skips the label when the member is `EMPTY`.

```python
# ✅ delivery/domain/review_verdict.py
from enum import Enum


class ReviewVerdict(Enum):
    EMPTY = None
    APPROVE = "approve"
    MINOR = "minor"
    BLOCKING = "blocking"
    BLOCKED = "blocked"
```

```python
# ✅ delivery/infrastructure/github_slice_repository.py
failure_cause = AgentRunCause(label_suffix(node, _FAILURE_LABEL_PREFIX))

failure_labels = (
    [f"{_FAILURE_LABEL_PREFIX}{a_slice.failure_cause.value}"]
    if a_slice.failure_cause is not AgentRunCause.EMPTY
    else []
)
```

### Rules common to both variants

- The domain always operates with `enum` types, never with `strings` or `None`.
- `Command`s and `Query`s declare these fields as `str` (basic types). The **handler** converts the `str` into the domain `enum` before interacting with the aggregate (`EntryKind(command.kind)` in `AppendJournalEntryCommandHandler`).
- Command tests assert with `strings` to check the edge contract.

## Slice state machine

The slice life cycle is **domain**, not infrastructure. The `Slice` aggregate is the only owner of its transition table and of every guard; it does no I/O. Each transition is a method that checks the allowed source states and raises `IllegalSliceTransitionError` otherwise:

| Transition | Guard | Allowed sources | Target |
|---|---|---|---|
| `dispatch()` | `can_be_dispatched()` | PENDING | DISPATCHED |
| `start_review()` | `can_start_review()` | DISPATCHED, CHANGES_REQUESTED | UNDER_REVIEW (clears the verdict) |
| `complete_review()` | `can_complete_review()` | UNDER_REVIEW | PR_OPEN |
| `block()` | `can_be_blocked()` | UNDER_REVIEW | BLOCKED |
| `request_changes()` | `can_request_changes()`, `can_address_changes(automatic, max_review_rounds)` | UNDER_REVIEW, PR_OPEN, BLOCKED | CHANGES_REQUESTED |
| `mark_merged()` | `can_be_merged()` | DISPATCHED, UNDER_REVIEW, CHANGES_REQUESTED, PR_OPEN, BLOCKED | MERGED |
| `close_without_merge()` | `can_be_closed_without_merge()` | DISPATCHED, UNDER_REVIEW, CHANGES_REQUESTED, PR_OPEN, BLOCKED | FAILED |
| `fail(cause)` | — | DISPATCHED, UNDER_REVIEW, CHANGES_REQUESTED | FAILED (with `failure_cause`) |

Every transition except the one to `FAILED` resets `retries` and `failure_cause`. Besides the guards, the aggregate answers the questions the detectors and handlers ask: the phase (`is_implementing()`, `is_under_review()`, `is_addressing_changes()`, `is_in_review_phase()`, `is_in_progress()`, `is_merged()`, `Slice.tracks_pull_request_in(status)`), the review (`needs_a_human_decision()`, `deserves_a_correction(max_review_rounds)`, `awaits_its_review_summary(max_review_rounds)`, `has_a_review_outcome()`, `awaits_requested_changes()`, `pending_directives()`, `addressed_directives_without_mark()`, `taken_directives()`, `has_correction_after_review()`, `lacks_correction_after_review()`, `declines_the_changes()`, `lacks_review_phase_artifact()`, `misses_verdict_or_correction()`), the merge (`is_auto_mergeable()`) and the dependencies (`dependencies(slices)`, `is_dispatchable(slices)`). It records runs and rounds with `record_agent_run(run)`, `retry_agent_run(run)`, `consume_review_round()`, `clear_review_rounds()` and `anchor_pull_request(number)`. `SliceVerification` (`start()`, `conclude()`, `fail(cause)`, with `can_start()` and `can_conclude()`) and `Lesson` (`learn(...)` and `discard()`, only from `IN_PROGRESS`) follow the same pattern with their own `IllegalVerificationTransitionError` and `IllegalLessonTransitionError`; `Lesson.close()` only marks the lesson's issue as closed.

```
PENDING → DISPATCHED → UNDER_REVIEW → PR_OPEN → CHANGES_REQUESTED → UNDER_REVIEW → PR_OPEN → MERGED (=DONE)
                ↓                          ↓                ↓
              FAILED   (terminal until human intervention; before that, capped retry of the recoverable causes)

              UNDER_REVIEW → BLOCKED → CHANGES_REQUESTED   (waits for a human decision, with the PR alive)
              UNDER_REVIEW → CHANGES_REQUESTED             (automatic correction, while rounds remain)
              CHANGES_REQUESTED → UNDER_REVIEW             (re-review of every correction)
```

After the PR opens, the loop dispatches an **automatic pre-human reviewer** (`DISPATCHED → UNDER_REVIEW`); when it leaves its summary comment (marker `<!-- grooveloop:review -->`), the slice moves to `PR_OPEN` (waiting for the human). **Every correction ends with a review:** the corrected PR, whether the loop or the human asked for it, always goes back to the reviewer (`CHANGES_REQUESTED → UNDER_REVIEW`), so the current verdict is always the one for the latest code.

Transition triggers (the table is the specification; any transition not listed is **illegal** and is rejected by the aggregate):

| Source | Trigger | Target |
|---|---|---|
| PENDING | the loop dispatches the agent | DISPATCHED |
| DISPATCHED | the loop anchors the PR and dispatches the reviewer | UNDER_REVIEW |
| DISPATCHED | the agent fails, or is interrupted with no attempts left | FAILED |
| UNDER_REVIEW | the reviewer fails, or is interrupted with no attempts left | FAILED |
| UNDER_REVIEW | the reviewer leaves the summary comment | PR_OPEN |
| UNDER_REVIEW | the reviewer marks `review:blocked` | BLOCKED |
| UNDER_REVIEW | the reviewer marks `review:blocking` and rounds remain | CHANGES_REQUESTED |
| PR_OPEN | the human requests changes | CHANGES_REQUESTED |
| CHANGES_REQUESTED | the PR has commits after the review, or a no-changes reply to a human directive, and the loop dispatches the reviewer | UNDER_REVIEW |
| CHANGES_REQUESTED | the agent fails addressing the changes, or is interrupted with no attempts left | FAILED |
| PR_OPEN | the human merges the PR | MERGED |
| PR_OPEN | the human closes the PR without merging | FAILED |
| DISPATCHED | the human merges the PR before `pr_open` is recorded | MERGED |
| UNDER_REVIEW | the human merges the PR during the review | MERGED |
| CHANGES_REQUESTED | the human merges the PR | MERGED |
| DISPATCHED | the human closes the PR without merging before `pr_open` is recorded | FAILED |
| UNDER_REVIEW | the human closes the PR without merging during the review | FAILED |
| CHANGES_REQUESTED | the human closes the PR without merging | FAILED |
| BLOCKED | the human writes `/grooveloop-implement` | CHANGES_REQUESTED |
| BLOCKED | the human merges the PR | MERGED |
| BLOCKED | the human closes the PR without merging | FAILED |

**Manual relabeling is outside the aggregate.** A human can change the state label of a sub-issue at any time: `blocked` → `pr_open` to unblock a slice, `failed` → `pending` to retry it, `pending` → `blocked` to pause a Story. The repository reads whatever label is there; the aggregate does not see the change as a transition.

Rules:

- **`FAILED` is terminal until human intervention; before reaching it, the loop retries the recoverable causes with a cap** ([ADR-0009](../adr/0009-failed-is-terminal-with-bounded-retry-first.md)). An implement, a reviewer or a correction whose run is `INTERRUPTED` is dispatched again without changing state (`DISPATCHED`, `UNDER_REVIEW` or `CHANGES_REQUESTED`) and without spending a review round: it gets a new run in `run:<id>` and the label `retry:N` with the attempts spent in the phase, which disappears on every transition except the one leading to `FAILED`, at the earliest 2 min × 4ⁿ after the end of the previous run, up to `--max-retries`. An implement whose run exits with 0 without opening the PR, a reviewer that exits with 0 without a verdict or summary comment, and a correction that exits with 0 without commits after the review (nor, for a human directive, a no-changes reply) are **resumed** with the same rule (`AgentRunner.resume`, in the worktree of the previous run) and, if the run cannot be resumed, dispatched again; with no attempts left they move to `FAILED` with `failure:incomplete`. With no attempts left, or with a `FAILED` run, the slice moves to `FAILED` with the label `failure:<cause>`. The retry rule (`RetryPolicy`) lives in `shared`; the cap and the wait bound the API quota burned by a prolonged outage.
- **`BLOCKED` is terminal until human intervention, but with the PR alive and without connoting a breakdown.** It is reached by the automatic reviewer's `review:blocked` verdict, reserved for findings that require a design decision from the human. The loop starts nothing on its own on a blocked slice; the way out is to write `/grooveloop-implement` on the PR (`BLOCKED → CHANGES_REQUESTED`, and the loop addresses the decision), merge, close the PR, or relabel the sub-issue from `blocked` to `pr_open` by hand.
- **A round is an automatic correction.** `--max-review-rounds N` (default `3`) caps how many times the loop asks for corrections on its own after a `review:blocking` verdict; the sub-issue carries the spent ones in the label `review-round:N`. With no rounds available, the blocking verdict leaves the slice in `PR_OPEN`, waiting for the human. The `blocked` verdict does not spend a round, and the human channel (`/grooveloop-implement`) has no limit and **clears** the `review-round:N` label when it takes over, so an automatic round spent in a previous cycle is not inherited when the human steps in later. The reviewer's summary comment is the change request of the automatic channel: the loop does not spend a round until it is published, and the commits after that instant are the ones that send the slice back to the reviewer (`CHANGES_REQUESTED → UNDER_REVIEW`), just like the ones after a `/grooveloop-implement` in the human channel. With N rounds there are at most N+1 reviews per human intervention.
- **The loop marks the `/grooveloop-implement` directives it consumes.** The marks are the loop's own reactions on the directive comment, read into `ReviewComment.marks`: `DirectiveMark.TAKEN` (👀) and `DirectiveMark.ADDRESSED` (🚀); a reaction of the same content by another account is not a mark. When `AddressReviewChangesCommandHandler` dispatches a human correction, it marks every `pending_directives()` as taken, before dispatching; when `ReviewPullRequestCommandHandler` sends a correction back to the reviewer, it marks the `taken_directives()` (👀 without 🚀) as addressed. The marks are written through the `DirectiveMarker` port, never by the agents and never by `save`. The automatic channel marks nothing. On a PR with any marked directive, a directive is pending if and only if it has no 🚀, so removing the 🚀 by hand re-opens it, and only the marked directives are review instants in `PullRequest.has_commits_after_review()`: a directive written during the correction (without 👀) neither holds the re-review nor gets 🚀, and goes into the next round. The review instant of a taken directive is the instant of the loop's 👀 (`ReviewComment.taken_at`, which `GithubSliceRepository` reads only for the directives with 👀 and without 🚀), not the instant the directive was written: a commit newer than the directive and the summary but older than the take does not send the correction back to the reviewer before it starts. GitHub keeps one reaction per account and content, so marking a directive with a mark it already carries (a directive taken again after its 🚀 was removed) refreshes the reaction (`GithubDirectiveMarker` removes it and adds it again, and forgets the cached take instant): the review instant is the one of the last take, not the first one. On a PR without marks, a directive is pending while no commit is newer than it (`PullRequest.has_unaddressed_comments()`); the summary takes no part in that decision, so the summary of the re-review that follows a correction does not re-open the directive it addressed. The first correction that marks a PR also marks as addressed the directives that rule already counted as addressed (`addressed_directives_without_mark()`), so they do not become pending once the PR has marks.
- **A blocking verdict with a round left waits for its summary while the reviewer is still alive.** The reviewer writes the verdict label before the summary comment, so there is a gap of tens of seconds in which the label is there and the summary is not yet. A tick inside that gap does not close the review: the slice stays in `UNDER_REVIEW` until the summary appears (and then spends a round) or until the reviewer's run ends without publishing it (and then moves to `PR_OPEN`, without spending a round). Without the live-run limit, a reviewer that died after the label would leave the slice in `UNDER_REVIEW` forever.
- **A human directive can be addressed without changes.** The correction of a `/grooveloop-implement` ends with commits **or** with a reply in the conversation of the PR that gives the reason and ends with the marker `<!-- grooveloop:no-changes -->` (`PullRequest.no_changes_reply_at`, the latest such comment). The reply is a correction (`has_correction_after_review()`) only when the PR has taken directives (👀 without 🚀) and the reply is newer than the review instant, so the automatic channel, which takes no directive, still needs commits. With that reply the loop sends the slice back to the reviewer and marks the taken directives as addressed, like a correction with commits; `ReviewTask` tells the reviewer that the developer declined to change code (`declines_the_changes()`: the reply without commits after the review) so it judges whether the reason holds. The reply also counts as the last change of the PR for `has_a_fresh_review_summary()`, so the summary of the previous review does not close the re-review. A correction of a human directive that ends with neither is resumed asking to push or to explain.
- **The reviewer checks every correction.** With commits after the review, the slice goes back to `UNDER_REVIEW` and the reviewer runs again on the already anchored PR, without looking at the rounds. Starting the review clears the `review:*` label from the previous cycle, so the verdict the loop reads is always the one from the current cycle; and a summary comment older than the last commit no longer closes the review, so the stale summary from the previous round does not move the slice to `PR_OPEN` early. The closing review with `review:blocking` and no rounds left leaves the slice in `PR_OPEN` for the human; with rounds left, it dispatches another correction.
- **merge = approve, close = reject:** GitHub's native semantics are reused as the decision signal; the loop detects the merge/close and transitions. The review lives 100% in the GitHub web UI.
- **With `--auto-merge`, the loop merges the approved PR.** `Slice.is_auto_mergeable()` (slice in `PR_OPEN` with verdict `approve` or `minor`) decides which PR is a candidate; `MergePullRequestCommandHandler` only squash-merges it if the `PullRequestMerger` port reports it as `Mergeability.CLEAN`, and otherwise the slice stays in `PR_OPEN`. The loop does not record the merge: the merge detector recognizes it on the next tick, like a human's. Without the flag, the loop does not query mergeability.
- **Merge and close are recognized from any intermediate state.** The human can merge or close the PR between two ticks, before any of them records the intermediate `pr_open` (the `Closes #N` closes the sub-issue and leaves the slice in `dispatched`). That is why `MERGED` and `FAILED` are reachable from `DISPATCHED`, `UNDER_REVIEW`, `PR_OPEN`, `CHANGES_REQUESTED` and `BLOCKED`: recognizing a resolved PR (merged or closed without merging) marks the slice in its correct terminal state without depending on having recorded the previous `pr_open`.

## Ordering and dependencies (DAG)

- The order inside a Story is the `SliceOrder` VO of `slicing`, which becomes the `order:N` label; `SliceRepository.search()` returns the slices of a Story sorted by it.
- Dependencies between slices form a **DAG**, not a linear list: a slice can depend on several earlier ones. In `slicing` they are positions (`depends_on: list[SliceOrder] | None`); in `delivery` they are sub-issues (`depends_on: list[SliceId] | None`).
- `depends_on = None` (the Spec has no `**Depends on:**` bullet for the slice) means the slice depends on **every earlier slice** of the Story; `[]` (`none`) means it depends on nothing.
- A slice is **dispatchable** only when it is `PENDING` and **all** its dependencies are in `MERGED` (`Slice.is_dispatchable(story_slices)`). Slices with no dependencies between them (parallel) are dispatched together.
- A Story never has more than `--max-parallel-slices` (default `3`) slices in progress: `ParallelSliceLimit.is_reached_by(story_slices)` counts the ones in `DISPATCHED`, `UNDER_REVIEW`, `PR_OPEN`, `CHANGES_REQUESTED` or `BLOCKED` (`Slice.is_in_progress()`). A dispatchable slice waits until one of them is merged or closed.
- A dependency always points to a slice of the same Story. A dependency on an issue outside the Story is never resolved (`dependencies()` returns `None`), so the slice is never dispatchable and the loop gives no warning.
- "Which slices can I dispatch now" needs the whole Story, so it is answered by `NextDispatchableSlicesQueryHandler`: it searches the slices of the Story and keeps the ones for which `is_dispatchable(slices)` holds.

## Ports

- Domain interfaces with **ABC** and `@abstractmethod`. Each port in its own file, in the `domain/` of the context that owns it. The ports of the application layer (`QueryBus`, `EventDispatcher`, `Probe`) live in `shared/application/`.

Project ports: **one repository per aggregate** — `StoryRepository` (`slicing`), `SliceRepository` (`delivery`), `SliceVerificationRepository` (`verification`), `LessonRepository` (`learning`) and `JournalEntryRepository` (`journal`) —; the read ports `AgentSessionRepository` (`delivery`) and `AgentRunContextRepository` (`journal`); the context ports `SliceLabels`, `PullRequestMerger`, `DirectiveMarker`, `MergedSliceSignal`, `LearnSignal`, `RefinementResult` and `ConventionsPullRequestStatus`; and the `shared` ports listed in `architecture.md` (`Clock`, `AgentRunner`, `AgentRunnerRegistry`, `AgentCommand`, `AgentLogReader`...). See [ADR-0004](../adr/0004-ports-and-adapters.md). There is no "god" repository spanning several aggregates.

### Repository method signatures

- `save(entity: Entity) -> None`
- `find(id: EntityId) -> Entity | None`
- `find_by_<unique_key>(value: ValueObject) -> Entity | None` — lookup by another unique key of the aggregate (`LessonRepository.find_by_source_pull_request`).
- `search(*optional_filters) -> list[Entity]`

A repository only declares the methods its callers use (`JournalEntryRepository` has no `find`).

### Simple criteria in search()

**Rule:** A single `search()` per repository that accepts all filters as optional kwargs with default `None`. Each new criterion is added as one more parameter, never as a `search_xxx` method or as a `find_by_xxx` when the criterion is not a unique key. Filters combine with AND; `None` means "do not filter by this criterion". The types are domain types (VOs, enums, `bool`), not `str`. A filter that only makes sense with a value (the `repo: str` of the journal, which scopes the files on disk) is a required positional parameter instead.

```python
# ✅ delivery/domain/slice_repository.py
class SliceRepository(ABC):
    @abstractmethod
    def search(
        self, story_id: StoryId | None = None, status: SliceStatus | None = None, open: bool | None = None
    ) -> list[Slice]: ...
```

`open=True` keeps the slices whose sub-issue is open, `open=False` the closed ones and `None` both.

### Unique-key lookups (`find` / `find_by_<UK>`) vs search criteria (`search`)

**Rule:** `find(id)` and `find_by_<UK>(...)` are lookups by a **unique key** of the aggregate. They return `Entity | None`. `search(...)` groups all the filter criteria that combine with AND and returns `list[Entity]`.

```python
# ✅ slicing/domain/story_repository.py
class StoryRepository(ABC):
    @abstractmethod
    def find(self, id: StoryId) -> Story | None: ...

    @abstractmethod
    def save(self, story: Story) -> None: ...

    @abstractmethod
    def search(self, status: StoryStatus | None = None, open: bool | None = None) -> list[Story]: ...


# ✅ learning/domain/lesson_repository.py
class LessonRepository(ABC):
    @abstractmethod
    def find(self, id: LessonId) -> Lesson | None: ...

    @abstractmethod
    def find_by_source_pull_request(self, source_pull_request: SourcePullRequest) -> Lesson | None: ...

    @abstractmethod
    def save(self, lesson: Lesson) -> None: ...

    @abstractmethod
    def search(self, status: LessonStatus | None = None, story_id: StoryId | None = None) -> list[Lesson]: ...
```

### Criteria vs projections in query ports

A **query port** is a read port with no `save()`, no identity and no life cycle (e.g. `AgentSessionRepository`, which reads the instrumentation run-dirs). The single `search()` rule governs its **criteria**, not its projections.

**Rule:** A **criterion** narrows which rows the search returns without changing the returned type: it goes as an optional kwarg of the existing `search()`. A **projection** changes the returned type because it answers a different question: it justifies its own `search_<projection>()` search, and only in query ports. Each search returns a **total** type; the richer projection **composes** the poorer one instead of mutilating it (`AgentSessionTranscript` holds its `AgentSession`).

```python
# ✅ delivery/domain/agent_session_repository.py
class AgentSessionRepository(ABC):
    @abstractmethod
    def search(self, repo: str, slice_id: SliceId | None = None) -> list[AgentSession]: ...

    @abstractmethod
    def search_transcripts(self, repo: str, slice_id: SliceId | None = None) -> list[AgentSessionTranscript]: ...
```

## Time: the `Clock` port

The domain never reads the system time directly. Every notion of "now" comes through the `Clock` port.

```python
# ✅ shared/domain/clock.py
from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
```

- The system adapter (`SystemClock`) returns the real time; in tests a `Clock` with a fixed instant is injected (`clock_at(now)` in `tests/playground/shared/infrastructure/clock.py`).
- Domain functions that depend on time receive the instant as a parameter (`RetryPolicy.is_due(retries, finished_at, now)`); the handler or the adapter reads it from the `Clock`.
- This makes the transitions and the tests deterministic, and avoids `datetime.now()` scattered through the code.

## Events

Events **are not emitted by aggregates or published when a command finishes**, and **are not persisted** (there is no broker or outbox). See [ADR-0006](../adr/0006-events-without-broker-detected-by-polling.md).

- An `Event` is a **`frozen` dataclass** that inherits from `shared/domain/event.py`'s `Event`: an in-memory signal of an actionable condition (e.g. `SliceReadyToDispatch(slice_id)`, `PullRequestMerged(slice_id)`, `ImplementationInterrupted(slice_id, run_id)`). No `channel` and no serialization (there is no broker).
- It is defined in `domain/events.py` of the **context that reacts** to that event.
- The **producers** are the **detectors** (infrastructure), which read GitHub or the local run-dirs on each tick; the **consumer** is an `EventHandler` that invokes a command (see `infrastructure.md`).
- There is no `EventProducer` or `EventCollector`: the domain does not know the event mechanism.

## Anti-patterns

- ❌ `search_by_status`, `find_slice_by_story` methods — they are optional filters of `search()`, not new methods. Exception: `find_by_<UK>` when the column is a unique key of the aggregate.
- ❌ Citing the single `search()` rule to reject a new projection — that rule governs criteria, not returned types.
- ❌ Hanging a computation method off a port that returns collections without identity, correlated by position with the output of `search()` — return a composite type from its own projection.
- ❌ Stitching two reads of the same port with `zip(..., strict=True)` — the source state can change between both calls.
- ❌ A boolean parameter in `search()` that decides whether the returned object travels complete — model two projections, each one total.
- ❌ `search()` filters without default `None`, or that distinguish "do not filter" from "filter by empty value".
- ❌ `search()` receiving `str` in filters that the domain models as a VO or enum — the handler casts the external input.
- ❌ `Optional[Enum]` in aggregate properties when the enum models the "absent" state — use Variant B (plain `Enum` with an `EMPTY = None` member).
- ❌ Comparing `a_slice.status` in a handler or a detector to decide a transition — ask the aggregate's guard (`can_be_merged()`, `can_start_review()`...). Filtering a `search()` by `status` is a criterion, not a decision.
- ❌ Changing `_status` outside the aggregate's transition methods.
- ❌ Auto-retry of a slice in `FAILED` — it is terminal until human intervention; the capped retry happens before reaching it.
- ❌ Reading `datetime.now()` in domain or application — use the `Clock` port.

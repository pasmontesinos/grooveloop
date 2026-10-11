# ADR-0009: `Failed` is terminal; before reaching it, the loop retries the recoverable causes with a cap

## Status

Accepted — 2026-10-01

## Context

The original rule was "`Failed` with no auto-retry": any run that ended with `[AGENT_EXIT] ≠ 0` moved the slice to `failed`, and only a human relabeling it recovered it. It avoided loops that burn API quota, but it treated a failure of the work the same as an outage unrelated to it.

In 606 runs over 30 days, 17 ended because of transient infrastructure (529 overloaded, network, external SIGTERM, crash without a `result` event) and all of them ended in `failed`. Whoever operates the loop over several repositories does not watch it continuously, so each outage leaves a slice stopped until someone notices.

The log reader already declares the run verdict with its cause (`AgentRunVerdict`): `INTERRUPTED` for the recoverable signatures and `FAILED` for the 401, the session limit and any unknown signature.

## Decision

- **`Failed` is still terminal until human intervention.** The loop never starts anything on a slice in `failed`.
- **Before reaching `failed`, the loop retries the recoverable causes with a cap.** An `INTERRUPTED` run does not change the slice state: the loop dispatches a new run of the same phase, which replaces `run:<id>`, and writes in the `retry:N` label the attempts spent in the phase.
- **The cap is `--max-retries`** (default 2). With `--max-retries 0` the loop behaves as before: the interrupted run moves the slice to `failed`.
- **Growing wait.** Attempt N+1 starts at the earliest 2 min × 4ⁿ after the end of the previous run (2 min, 8 min). The end is the last write to `agent.log`.
- **Idempotency per run.** The command only acts if the slice's `run:<id>` is still the run that was interrupted; the new dispatch changes that run, so two ticks on the same interrupted run dispatch again only once.
- **With no attempts left, or with a `FAILED` cause, the slice moves to `failed` with the label `failure:<cause>`.** A signature the reader does not know is `FAILED`: by default it is not retried.
- **Recovery never deletes work.** The implement re-dispatch mentions in the prompt the branch of the previous attempt if it reached `origin`.
- **Split between contexts.** The run verdict and the retry rule (`RetryPolicy`) live in `shared`; each context has its detector and its command.

## Consequences

- An API or network outage no longer leaves the slice in `failed`: the loop relaunches it on its own, at most `--max-retries` times per phase.
- A real failure of the work still ends in `failed`, visible, and now with its cause in `failure:<cause>`.
- The cost of a retry is one more run of the phase. The cap and the growing wait bound the spend during a prolonged outage.
- The covered phases are implement, the automatic review (`review_slice`, in `under_review`) and the correction (`address_review`, in `changes_requested`). The retry of a review phase does not spend a `--max-review-rounds` round, and `retry:N` disappears as soon as the slice changes phase. An implement that ends with exit 0 without opening the PR (`INCOMPLETE`) is resumed under the same rule: the loop launches `claude --resume <session_id>` in the worktree of the previous run, in a new run-dir with `resumed_from` and `workdir` in its `run.json`, and spends from the same `retry:N`; without a `session_id`, without a worktree or with opencode the attempt is a re-dispatch, and with no attempts left the slice moves to `failed` with `failure:incomplete`. With `--max-retries 0` the implement without a PR stays in `dispatched`, as before. The automatic review that ends with exit 0 without a verdict label or summary comment and the correction that ends with exit 0 without commits after the review are resumed the same way, each with its short instruction and without spending a `--max-review-rounds` round; the review that already wrote its label is not resumed even if the summary is missing. With no attempts left they move to `failed` with `failure:incomplete`, and with `--max-retries 0` they stay in their phase, as before.
- Verification (`verify_deploy`) applies the same rule in its context: an `INTERRUPTED` run without a report is dispatched again with the label `verif-retry:N` (the sub-issue already carries delivery's `retry:N`), and with no attempts left or with a `FAILED` cause the verification moves to the terminal state `verification:failed` with `failure:<cause>`. `verification:failed` counts as pending for closing the Story, just like `verification:running`. A `verify_deploy` that ends with exit 0 without a report is resumed with the same rule, spending from `verif-retry:N`, and with no attempts left moves to `verification:failed` with `failure:incomplete`.

# Slicing heuristics, validity and production safety

Reference for the `grooveloop` slicing contract. The artifact format lives in `SKILL.md`.

## Philosophy

Each change reaches production in the smallest slice that delivers value or reduces risk. Small slices are reviewed, deployed and reverted faster, and with a smaller blast radius.

## Principles

- **Atomic:** a commit, a PR and a deploy do a single thing.
- **Vertical by default:** each slice crosses every layer needed to deliver value end to end. It is the preferred way to slice.
- **Horizontal when needed:** if the vertical slice comes out too big for one PR, split it horizontally (by layer, by step, by rule). Horizontal splitting is not an anti-pattern: it is the tool to stay within size.
- **Reversible:** the slice is reverted with `git revert`, with no reverse migration or manual intervention.
- **Deployable on its own:** it works in production even if the following ones are never merged.

## Target size

- **300-400 lines of diff per PR at most.** This is the hard limit. Days of work do not count.
- If a vertical slice exceeds that size, split it until it fits.
- If you cannot see how to fit with a single vertical cut, do not force it: combine heuristics.

## Validity criteria

Before opening a PR, the slice meets the five conditions:

1. **Reversible.** `git revert` leaves the system consistent. If the slice replaces behavior already in production, reversible includes **reversible at runtime**: going back to the previous behavior without a redeploy, with a feature flag or expand-contract.
2. **Deployable on its own.** It does not depend on unmerged code or on a specific deploy order.
3. **No hidden work in progress.** It does not introduce dead classes, fields or branches that only make sense in a future slice.
4. **Delivers value or reduces risk.** It delivers behavior, prepares infrastructure, or unblocks the next slice.
5. **Within the size limit.** The diff fits in 300-400 lines.

## Slicing heuristics, in order of preference

Apply the first one that works. If a single one is not enough to fit the limit, combine it with another, usually vertical plus horizontal.

1. **Workflow steps.** Split by steps. Deliver the minimal happy path first, then the optional steps.
2. **Happy path and edge cases.** First the main case without sophisticated error handling. Validations, failures and retries go in later slices.
3. **Input or data variations.** Support one type, format or region first. Add the others later.
4. **Business rules.** Implement the default rule. Exceptions and special calculations go separately.
5. **CRUD.** Read before Create, Create before Update, Update before Delete, depending on value.
6. **Horizontal by layer.** When the vertical slice does not fit in one PR: infra or migration, domain, application and presentation in separate PRs.
7. **Effort, from simple to complex.** Manual version or hardcoded values first, automation later.
8. **Deferrable cross-cutting capabilities.** Performance, advanced telemetry, internationalization and fine-grained accessibility get their own slices, when they add value, without blocking the core.
9. **Spike.** If there is technical uncertainty, a time-boxed spike that produces knowledge, not production code, is a valid and explicit slice.

## Infra and migration isolation

**Rule:** schema migrations and infrastructure changes go in PRs separate from the application code that consumes them.

Reasons:

- It lets you deploy the migration in one window, observe, and deploy the code in another.
- It lets you roll back the code without touching the database, and vice versa.
- It reduces the blast radius of each deploy.

Typical order to add a new field:

1. **PR-1, infra:** migration, nullable column, updated model.
2. **PR-2, domain and application:** value objects, entity, use case, views and tests that use the new field.
3. **PR-3, cleanup, if applicable:** backfill, removal of old columns, schema contraction.

## Expand, migrate, contract

For changes that modify existing behavior, cut the slices like this:

1. **Expand:** add the new field, table or path without removing the old one.
2. **Migrate:** enable the new path with a feature flag, dual write or dual read.
3. **Contract:** remove the old path once nobody uses it.

Other safety techniques: branch by abstraction for large replacements; dark launching to validate without exposing the user; backward compatible APIs before breaking contracts.

## When parallel changes are mandatory

If the slice **replaces** something already in production, parallel changes with a feature flag are the default, not an option. Triggering cases:

- Replacing an adapter of a port in use: LLM, repository, external client, queue, database.
- Switching external provider: APIs, identity providers, payment gateways.
- Changing business rules or algorithms observable by the user.
- Any change whose failure depends on something non-deterministic at runtime: network, external APIs, quotas, latency.

Replacing in place is acceptable only if the plan justifies it with at least one of these reasons:

- The affected path is not exposed to end users or to downstream systems, for example local tooling or development scripts.
- There is no previous working implementation. It is the first time that behavior is introduced.
- Switching at runtime is impossible, or adds more risk than the deploy. This must be justified technically.

If none applies, **the plan splits the change into at least two slices**: expand, which adds the new path behind the flag with the old path active by default, and contract, which removes the old path after an observation period with the flag at 100%.

## Slicing anti-patterns

- Mixing a schema migration with the code that uses it in the same PR.
- Mixing a refactor with a feature in the same PR.
- Replacing in place an adapter or provider already in production, without a flag or expand-contract, when a previous working implementation exists.
- Slices that only add scaffolding and are not deployable on their own.
- Adding fields, methods or classes "that we will need in the next slice".
- PRs that depend on a specific merge order not to break production.
- Naming slices by technical layer when the vertical cut did fit within the limit.
- Leaving the riskiest case for last.
- Titles with "and" or "or", which hide several features.
- Verification in prose, without the full command and its executable assert.
- Different verification commands in the Spec and in the slice plan.
- Treating the observable verification as a requirement to approve the PR. It runs on `master`, already merged.

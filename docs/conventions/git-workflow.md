# Git Workflow

## Branches

- **NEVER commit directly to `master` or `main`.**
- Before any commit, check the current branch with `git branch --show-current`.
- If we are on `master` or `main`, create a new branch before committing.
- Branch name format: `<type>/<slug>` (e.g. `feat/auto-merge-approved-pull-requests`, `fix/stalled-run-detection`).

## Commits (Conventional Commits)

Format: `type(scope): description`

**Allowed types:** `feat`, `fix`, `refactor`, `test`, `style`, `chore`, `docs`

**Checklist BEFORE committing:**

1. `git branch --show-current` — check that we are NOT on `master`/`main`
2. `make fix-linting` — fix format and linting (`uv run ruff`)
3. `make check-types` — check static typing (`uv run mypy`)
4. `make test` — run the full suite (`uv run pytest`)
5. `git diff --staged` — review the changes about to be committed

If any of steps 2-4 fails, fix it before committing.

**Examples:**

```
feat(cli): run the same preflight in doctor and before the loop starts
fix(learning): make the refinement idempotent and keep I/O out of the Lesson aggregate
refactor(delivery): close abandoned runs in their own tick step so detectors only read
```

### Pull Requests

**Checklist BEFORE creating a PR:**

1. `git branch --show-current` — check that we are NOT on `master`/`main`
2. `make fix-linting`
3. `make check-types`
4. `make test`
5. Push to the remote branch with `git push -u origin <branch>`

**Template:** If `.github/pull_request_template.md` exists, use its structure for the PR body. If not, the body includes: summary of the change, slice (if applicable), observable verification.

**PR title:** `<type>(<scope>): <description>` following Conventional Commits, without `[Added]`/`[Changed]` prefixes. If the team works with an external task identifier (Jira or other), it can optionally be prepended: `{TASK_ID} <type>(<scope>): <description>`. It is not mandatory.

## Releases

Versions follow [Semantic Versioning](https://semver.org/). While the version is `0.x`, a change to the contract with GitHub (spec format, labels, directives, report headings) or to the CLI flags bumps the minor version; anything else bumps the patch version.

The version lives in two places that must match: `version` in `pyproject.toml` and `version` in `plugins/grooveloop/.claude-plugin/plugin.json`. `tests/grooveloop/test_release_metadata.py` fails when they differ.

**To release:**

1. Open a Pull Request that bumps both versions, titled `chore(release): vX.Y.Z`, and merge it when CI is green.
2. Tag the merge commit on `master` and push the tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The `Release` workflow (`.github/workflows/release.yml`) checks that the tag matches both versions, runs the full validation, builds the distribution, publishes it to PyPI through Trusted Publishing (environment `pypi`) and creates the GitHub release with generated notes.

Never publish from a local machine and never store a PyPI token in the repository: Trusted Publishing is the only publishing path.

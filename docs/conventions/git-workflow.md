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

release-please (`.github/workflows/release-please.yml`) computes the version from the Conventional Commits on `master`. While the version is `0.x`:

- `feat` and `fix` bump the patch version.
- A contract or CLI flag change is marked as breaking (`feat!:`, or a `BREAKING CHANGE:` footer) and bumps the minor version.
- The other types do not release.

The version lives in five places that must match: `pyproject.toml`, `plugins/grooveloop/.claude-plugin/plugin.json`, the `grooveloop` entry of `uv.lock`, `.release-please-manifest.json` and the landing (`site/index.html`, the line marked with `<!-- x-release-please-version -->`). release-please bumps all five (`release-please-config.json`); `tests/grooveloop/test_release_metadata.py` fails when the plugin, the manifest or the landing differ from the package, and `uv sync --locked` fails when the lock does.

**To release:**

1. On every push to `master`, release-please opens or updates the Pull Request `chore(release): vX.Y.Z` with the bumped versions and the `CHANGELOG.md` entry.
2. Merge it when CI is green. release-please tags the merge commit and creates the GitHub release.
3. The tag runs the `Release` workflow (`.github/workflows/release.yml`): it checks that the tag matches the versions, runs the full validation, builds the distribution, publishes it to PyPI through Trusted Publishing (environment `pypi`, which waits for the approval of a reviewer) and attaches the distribution to the GitHub release.

release-please runs with the `RELEASE_PLEASE_TOKEN` secret, a fine-grained token with write access to contents and pull requests of this repository: with the default `GITHUB_TOKEN`, its Pull Request does not run CI and its tag does not run the `Release` workflow.

Never edit the versions by hand, never publish from a local machine and never store a PyPI token in the repository: Trusted Publishing is the only publishing path.

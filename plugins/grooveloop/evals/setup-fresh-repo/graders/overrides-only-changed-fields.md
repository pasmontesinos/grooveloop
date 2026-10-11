---
type: llm
weight: 2
---

- Proposes the file `.grooveloop/agents/developer.md`.
- That file is only a YAML front matter block between two `---` lines, with no text after the second one.
- It declares `context_files` with the four paths `docs/conventions/code-style.md`, `docs/conventions/domain.md`, `docs/conventions/testing.md` and `docs/conventions/git-workflow.md`.
- It does not declare `engine`, `model` or `skills`, because they do not change from the package profile.
- No proposed override includes a persona, instruction or description of the role.

---
name: conventions
description: This skill should be used when working with the convention files of a repository (`docs/conventions/`), to review them, improve them, create new ones, adapt them after a change of pattern or suggest improvements. It triggers on "review the conventions", "improve the style of testing.md", "add a convention about X", "update the domain convention", "what can be improved in the conventions", "refine the conventions", "conventions review", "conventions suggest", and when the grooveloop scribe codifies a review lesson.
---

# grooveloop:conventions

Reviews, refines, creates and adapts the convention files of the repository (`docs/conventions/`).

## Choose the operation

| The request is to... | Operation |
|---|---|
| Review or improve existing conventions, suggest changes | **Review and suggest** |
| Refine the style of one file | **Refine** |
| Create a new convention or section | **Create** |
| Update a convention after a change of pattern | **Adapt** |

If no file is named, start with **Review and suggest** to give context before acting.

## Autonomous mode

When no human is in the conversation (the grooveloop `scribe` codifying a lesson):

- Do not ask questions: skip the steps that wait for a decision and pick the minimal option.
- Use only **Create** or **Adapt**, limited to the rule the lesson brings.
- Apply the Style Reference to the text you write. Do not restyle sections you are not otherwise changing.
- Leave the summary in the reply the task asks for, not in the convention file.

## Style Reference

Canonical format of the convention files. Every creation or edit follows these rules.

### Efficiency principles

- Prefer complete, self-contained convention files. Split a file only when it covers clearly independent topics.
- Direct imperative, no justifications. The convention says **what to do**, not why. A justification belongs in separate human documentation.
- No preambles or intros. Nothing like "This document describes..." or "It is important to remember...". Go straight to the first H2 section.
- One canonical positive example per rule. More examples inflate tokens with no marginal value.

### File structure

- `# Title` (H1): the name of the topic, without article. E.g. `# Domain`, `# Testing`, `# Application`.
- `## Section` (H2): a concept or a group of related rules.
- Go straight to the first H2 section after the H1, with no introductory paragraph.
- H3 for subsections when there is a clear hierarchy.
- Three levels (H1 + H2 + H3) is the maximum. No H4+.

### Format of each rule

Use the `**Rule:**` prefix only when a section mixes explanatory context with directives, to tell the imperative instructions apart from the prose. If the whole section is directives (imperative bullet lists, signature tables), the prefix is noise: omit it.

Pattern with prefix (mixed section):

````markdown
**Rule:** {imperative or declarative description, one or two sentences ending with a period}.

```python
# ✅ path/to/file.py (optional)
{correct code, no explanatory comments}
```
````

Pattern without prefix (pure directives section):

```markdown
- They inherit from `EventCollector`.
- No *Entity* or *Aggregate* suffix.
- Every attribute is private (`_` prefix).
```

Format rules:

- A period at the end of every sentence.
- A blank line between the text of the rule and the code block.
- The `# ✅` block never carries explanatory comments; the rule already explains the pattern.
- If there is only a positive example and no relevant anti-pattern, omit the anti-patterns.

### Anti-patterns

Anti-patterns are written as **text bullets with ❌**, never as code blocks. Code under `# ❌` has a non-trivial chance of being reproduced, and it takes 5-10x the space of the bullet.

Exact pattern:

```markdown
## Anti-patterns

- ❌ Mocking value objects — use real instances
- ❌ A test with several unrelated asserts
- ❌ Global fixtures shared between modules
```

Rules:

- One line per anti-pattern, two sentences at most.
- If the alternative is not obvious, add it after ` — `.
- Group the anti-patterns in a single `## Anti-patterns` section at the end of the file.
- No code blocks in the anti-patterns under any circumstance.

### Ubiquitous Language section (optional)

For files that touch the domain (`domain.md`, `application.md`), include a ubiquitous language section when there are ambiguous terms.

Exact pattern:

```markdown
## Ubiquitous Language

- Enrollment = enrollment in a school year (not "registration")
- Guardian = legal guardian (not "parent")
```

Rules:

- Only terms with real ambiguity, or where the model tends to use wrong synonyms.
- Format: `ClassName = meaning (not "wrong synonym")`.

### Paths and names

- File paths inline in backticks: `` `{context}/application/commands/{handler}.py` ``.
- A path inside a code block: `# ✅ {package}/example/domain/example.py`.
- Class and method names as the code writes them. The prose in the language the existing convention files use.

### Tables

Use tables only for:

- Strategy matrices (e.g. layer → what to test → how to mock).
- Typical signatures of repository methods.
- Comparisons of approaches.

### What must not appear

- Introductory prose ("In this section we will see...", "It is important to remember...").
- Explanatory comments in the `# ✅` blocks.
- Docstrings or comments in the example code, unless they illustrate the rule itself.
- Rules duplicated across convention files.
- Code blocks in anti-patterns.
- Justifications or reasoning about why the rule exists.

## Operation: Review and suggest

Analyzes one or more convention files and presents prioritized suggestions. The human decides which to apply.

1. **Scope.** If a file is named, read it. If not, list every file in `docs/conventions/` and read them.
2. **Audit each file** against the Style Reference. Classify the findings:
   - **Style:** `**Rule:**` in pure directive sections (noise) or missing in mixed sections, wrong markers (`# Correct` instead of `# ✅`), anti-patterns as code blocks instead of ❌ bullets.
   - **Structure:** introductory prose, H4+ headings, paragraphs with no verifiable information, unneeded justifications.
   - **Content:** rules duplicated across files, sections on independent topics that could be split, rules that no longer match the current code.
3. **Present the suggestions grouped by file:**

   ```markdown
   ## Convention suggestions

   ### `docs/conventions/{filename}.md`

   | Priority | Section | Suggestion |
   |---|---|---|
   | High | {section} | {concrete description of the change} |
   | Medium | {section} | {concrete description of the change} |
   ```

   - **High:** directly affects the behavior of the model (anti-patterns in code, ambiguous rules).
   - **Medium:** improves token efficiency or clarity (removable prose, structure).
   - **Low:** cosmetic (format, minor consistency).
4. **Ask** which suggestions to apply: all of one file, only the high ones, individual ones, or none.
5. **Apply** the accepted suggestions with Edit and present a summary of the changes.

## Operation: Refine

Applies the canonical style to one convention file.

1. **Load the file.** If the name has no path, look in `docs/conventions/`.
2. **Audit the style** against the Style Reference:
   - `**Rule:**` where it adds nothing (pure directive section) or missing where it does (mixed section).
   - Code blocks marked `# Correct` / `# Incorrect` / `# Good` / `# Bad` instead of `# ✅`.
   - Code blocks used as anti-patterns.
   - Introductory prose with no useful information.
   - Explanatory comments in `# ✅` blocks that belong in the text of the rule.
   - H4+ headings.
   - Justifications of why a rule exists.
3. **Fix with Edit** each finding: add or remove `**Rule:**`, replace the markers with `# ✅`, turn `# ❌` blocks into ❌ bullets, remove prose with no verifiable information, move explanations from the `# ✅` block to the rule, and leave only the imperative instruction.
4. **Present the summary:**

   ```markdown
   ## Refinement: {filename}

   | Type | Description |
   |---|---|
   | Rule prefix | Added **Rule:** in section X |
   | Code marker | # Correct → # ✅ |
   | Anti-pattern | Code block → ❌ bullet |
   | Prose removed | Introductory paragraph with no useful information |

   **Total:** {N} changes
   ```

## Operation: Create

Creates a new section in an existing convention file, or a new file.

1. **Analyze the context.** If the file exists, read it to learn its sections, the style in use and where the new section goes.
2. **Write the content** following the Style Reference: `**Rule:**` only in mixed sections, anti-patterns as ❌ bullets at the end, names of the project's own classes and modules (never `Foo`/`Bar`), one positive example per rule.
3. **Insert it with Edit** at the end of the existing content, or create the file with Write.
4. **Show the content created.**

Principles:

- **Minimum needed:** if an existing rule already covers the pattern, do not duplicate it.
- **Real examples:** names from the project's domain.
- **One rule, one purpose:** do not combine two patterns in one rule.
- **Token-efficient:** direct imperative, no justifications, one example per rule.

## Operation: Adapt

Updates an existing convention to reflect a change in the project's pattern.

1. **Read the file** to find the affected section and rule.
2. **Identify the impact:** which part of the rule text changes, which `# ✅` blocks need the new pattern, and whether the ❌ bullets are still relevant.
3. **Apply the changes with Edit:** the rule text, the `# ✅` blocks, and the ❌ bullets that must change or go.
4. **Check consistency:** whether the change affects other convention files (e.g. `testing.md` referencing patterns of `domain.md`). Point it out in the summary.
5. **Present the summary:**

   ```markdown
   ## Adapted convention: {section} in {filename}

   **Before:** {description of the previous pattern}
   **After:** {description of the new pattern}

   ### Files possibly affected

   - `docs/conventions/{file}.md` — check references to the previous pattern
   ```

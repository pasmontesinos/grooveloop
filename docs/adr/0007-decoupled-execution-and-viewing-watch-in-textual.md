# ADR-0007: Decoupled execution and viewing — the Textual watch is the only viewer

## Status

Accepted — 2026-09-24

## Context

Today the loop can be viewed in two ways, with two modes each:

- `grooveloop loop --render` paints the panel inside the same process that runs the ticks (`WatchSession`), and `--no-tick` leaves it only observing.
- `grooveloop watch` paints the loop list and the repo panel in live mode, and with `--once` or without a TTY it prints a plain text frame and ends.

The four paths share a hand-made render on top of `rich`: `live_screen` (alternate screen and clipping to the height), `keys` (cbreak mode and key reading), `columns` (two-column layout with computed widths) and `watch_render` (Story tree with a width budget per session line).

The next viewer features do not fit in that render:

- **The Story journal**: a summary of the latest entries and a full view with scroll, because the bodies take several paragraphs.
- **Slices as a DAG**: a layered layout by topological level instead of a list.

Both need flexible layout, scroll and declarative keys. With the current render, each one requires computing widths, clipping and keyboard states by hand, multiplied by the four paths.

## Decision

- **The loop only executes.** `grooveloop loop` is a headless daemon. `--render`, `--no-tick`, `WatchSession` and the loop panel are removed.
- **The watch only displays, and it is a [Textual](https://textual.textualize.io/) app.** `grooveloop watch` is the only viewing interface. `--once`, the output without a TTY and the plain text render are removed.
- **The contract between the two is the state files.** The loop writes the snapshot (`snapshot.json`), the heartbeat (`heartbeat.json`), the runs (`run.json`, `agent.log`) and the journal. The watch only reads them. The watch does not run ticks, does not dispatch agents and does not import loop code.
- **A single render path.** Everything the watch paints comes out of the Textual app's widget tree. The `rich` renderables that are reused (for example, a `Tree`) live inside widgets, not as a parallel render.
- **`--screenshot` is a startup mode, not a viewer.** When a visual Story needs executable verification, `grooveloop watch --screenshot <file>.svg` starts the same app without a TTY, paints a frame, exports the SVG (`App.save_screenshot()`) and ends. It is added only when a Story needs it (YAGNI); the first candidate is the DAG.

### Transition

The replacement is local tooling with no downstream users, but the watch is used daily. That is why it arrives via expand/contract:

1. **Expand:** the Textual watch coexists with the current one behind `grooveloop watch --tui`.
2. **Contract:** when `--tui` matches the current watch, a slice removes the old watch, the flag and the loop panel.

The journal and the DAG are built on the Textual watch, not on the current render.

## Consequences

> **Update (2026-10):** The transition is complete: `--tui` and the hand-made render modules (`live_screen`, `keys`, `columns`) are gone, and `--screenshot` exists. `docs/loop-reference.html` is not part of this repository.

- **New runtime dependency:** `textual`. It is from the same author as `rich` and reuses it. Revises [ADR-0001](0001-stack-python-hexagonal-cli.md): the entrypoint is still a local CLI, with no server or port.
- **Asynchronous model only at the edge.** Textual runs on `asyncio`. The watch is presentation (`cli/`); domain and application stay synchronous and the watch uses them through their queries.
- **Code removed in the contract:** `live_screen`, `keys`, `columns`, the `loop_command` panel, `watch_session` and the part of `watch_render` and `loops_render` that the widgets do not reuse.
- **The viewer tests change shape.** They stop comparing text and move to `App.run_test()` with its `Pilot` (pressing keys, querying widgets).
- **Observable verification does not `grep` the watch.** What is data is verified with `gh`, `jq` on the state files, `grooveloop journal` and `grooveloop loop --once`. What is visual, when needed, with `grep` on the `--screenshot` SVG. The closed Issues and plans that used `watch --once` are not rewritten: their verification already ran.
- **The frames in `docs/loop-reference.html`** are no longer generated with `watch_render.render`. They are generated with `--screenshot` and go into the HTML as SVG.
- **The watch does not depend on the loop being alive.** If the loop dies, the watch shows the last written state and its age; if the watch dies, the loop keeps going.
- **Textual restores the terminal on exit**, also if the app fails, instead of leaving it in `-icanon -echo` as today.

## Alternatives considered

- **Keeping the current render on top of `rich`:** rejected. The full journal needs scroll and the DAG a layered layout; both require recomputing widths, clipping and keyboard states by hand in each path.
- **Web viewer (served HTML or file with reload):** rejected for now. It gives scroll, links and DAG edges almost for free, but it adds a server or JavaScript, stops working over SSH and in tmux, and needs its own process life cycle. If needed, `textual-serve` serves the same app in the browser without a second interface.
- **Textual only for the live mode, with the `rich` render for `--once` and without a TTY:** rejected. It keeps two render paths for the same data.
- **`prompt_toolkit`, `urwid` or `curses`:** rejected. They give flexibility, but they are lower level and do not reuse the `rich` renderables like Textual does.
- **Pager (`less -R`) for the full journal, on top of the current render:** rejected. It solves the journal, but not the DAG, and leaves the current render as the base of the next features.

from __future__ import annotations

from textual.theme import Theme

BACKGROUND = "#0f1419"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#6e7681"
FOCUS = "#58a6ff"
OK = "#3fb950"
WARNING = "#e3b341"
ERROR = "#f85149"
MERGED = "#d2a8ff"

STATUS_STYLES = {
    "pending": MUTED,
    "dispatched": FOCUS,
    "under_review": FOCUS,
    "pr_open": WARNING,
    "changes_requested": FOCUS,
    "blocked": ERROR,
    "merged": MERGED,
    "failed": ERROR,
}
OUTCOME_STYLES = {"running": FOCUS, "done": OK, "interrupted": WARNING, "failed": ERROR, "unstarted": MUTED}
_TINT_AMOUNT = 0.25


def tint(color: str, amount: float = _TINT_AMOUNT) -> str:
    over = _channels(color)
    under = _channels(PANEL)
    blended = [round(base + (top - base) * amount) for top, base in zip(over, under, strict=True)]

    return "#" + "".join(f"{channel:02x}" for channel in blended)


def _channels(color: str) -> list[int]:
    return [int(color[index : index + 2], 16) for index in (1, 3, 5)]


WATCH_THEME = Theme(
    name="grooveloop",
    primary=FOCUS,
    secondary=MERGED,
    accent=FOCUS,
    warning=WARNING,
    error=ERROR,
    success=OK,
    foreground=TEXT,
    background=BACKGROUND,
    surface=PANEL,
    panel=PANEL,
    dark=True,
    variables={"border": BORDER, "text-muted": MUTED},
)

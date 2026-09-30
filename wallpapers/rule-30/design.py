"""An elementary cellular automaton, Rule 30 by default, grown from a single cell in square cells."""

from typing import Literal

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_1, ACCENT_2, ACCENT_3, BG_ALT, UI, Canvas, Params, design, knob
from walldye.pixel import grid_runs


class Automaton(Params):
    rule: int = knob(default=30, choices=(30, 90, 110), doc="Wolfram code of the automaton")
    trace: Literal["column", "edges"] = knob(
        default="column", doc="cells picked out: the seed's column, or both edges of the growth"
    )


# Rule 90's center column dies after the seed, so it picks out its two always-live edges;
# Rule 110 grows one way only, so its seed column is its straight edge.
VARIANTS = {"rule-90": Automaton(rule=90, trace="edges"), "rule-110": Automaton(rule=110)}

CELL, CORE = 8, 18  # cell size; half-width of the brighter core band around the seed column
# Picked-out cells step down the accent ramp, from ACCENT at the seed to ACCENT_3, at these rows.
HEAD_ROWS = (40, 72, 104)
PALETTE = (None, BG_ALT, UI, ACCENT, ACCENT_1, ACCENT_2, ACCENT_3)  # empty, field, core, head


def evolve(rule: int, rows: int, cols: int, seed: int) -> NDArray[np.bool_]:
    """The first `rows` generations of the elementary automaton with Wolfram code `rule`, grown
    from one live cell at column `seed`, as a `(rows, cols)` grid. Growth past either side of
    the grid carries on in a margin, so the visible edge columns stay exact."""
    table = np.array([(rule >> k) & 1 for k in range(8)], dtype=bool)
    pad = rows + 1  # the pattern spreads at most one cell per row, so np.roll never wraps it
    row = np.zeros(cols + 2 * pad, dtype=bool)
    row[seed + pad] = True
    out = np.empty((rows, cols), dtype=bool)
    for j in range(rows):
        out[j] = row[pad : pad + cols]
        left, right = np.roll(row, 1), np.roll(row, -1)
        row = table[4 * left + 2 * row + right]
    return out


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Automaton]) -> None:
    # Right of center, leaving the upper left empty. The right flank runs off the right edge,
    # except on the widest screens, where the whole triangle fits and keeps clear of it.
    fx = 0.75 if s.w < 3 * s.h else 0.66
    seed = s.pick(landscape=(fx, 0), portrait=(0.7, 0), snap=CELL)
    rows, cols, c0 = s.h // CELL + 1, s.w // CELL + 1, int(seed.x) // CELL
    live = evolve(s.params.rule, rows, cols, c0)
    depth = np.arange(rows)[:, None]
    dist = np.abs(np.arange(cols) - c0)
    grid = np.where(live, np.where(dist <= np.minimum(depth, CORE), 2, 1), 0)
    head = 3 + np.searchsorted(HEAD_ROWS, np.arange(rows), side="right")[:, None]
    traced = (dist == 0) if s.params.trace == "column" else (dist == depth)
    grid = np.where(traced, np.where(live, head, 0), grid)
    grid_runs(s, grid, PALETTE, CELL)

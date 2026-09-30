"""Langton's ant on a cell grid, toned by when the ant first reached each cell."""

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_4,
    ACCENT_6,
    ACCENT_7,
    BG_ALT,
    UI,
    Canvas,
    design,
)
from walldye.pixel import grid_runs

type Grid = NDArray[np.int64]

CELL = 10
PAD = 40  # cells simulated past every edge, so the highway leaves the frame cleanly
# The highway starts near step 9977; its first periods keep the blob's tones so it grows out
# of the chaos before it lights up.
HIGHWAY_FROM = 10200
HEADINGS = ((0, -1), (-1, 0), (0, 1), (1, 0))  # mirrored, so the highway heads down and right
# 1-2 the blob (flipped under 4 times, and more), 3-4 the highway's inside, 5-8 its edges,
# faintest first
PALETTE = (None, BG_ALT, UI, ACCENT_6, ACCENT_7, ACCENT_4, ACCENT_2, ACCENT_1, ACCENT)


def walk(cols: int, rows: int, x: int, y: int) -> tuple[Grid, Grid, Grid]:
    """Run the ant from cell (x, y) of an empty cols x rows grid until it reaches the border.

    Returns, per cell, its final color (1 or 0), the step on which the ant first entered it
    (0 if never) and how many times it was flipped.
    """
    on = np.zeros((rows, cols), np.int64)
    first = np.zeros((rows, cols), np.int64)
    flips = np.zeros((rows, cols), np.int64)
    d, t = 0, 0
    while 0 < x < cols - 1 and 0 < y < rows - 1:
        t += 1
        d = (d + (-1 if on[y, x] else 1)) % 4
        on[y, x] ^= 1
        flips[y, x] += 1
        if not first[y, x]:
            first[y, x] = t
        x, y = x + HEADINGS[d][0], y + HEADINGS[d][1]
    return on, first, flips


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the ant's start: the blob sits a little left of center and low, so the highway has room to
    # run down and off to the right; wider screens move it further left, out of the middle, and
    # a portrait one up and left, since the highway leaves through the right edge there
    wide = s.w / s.h - 16 / 9
    start = s.pick(landscape=(0.47 - 0.05 * wide, 0.59), portrait=(0.36, 0.42), snap=CELL)
    cols, rows = s.w // CELL + 1, s.h // CELL + 1
    on, first, flips = walk(
        cols + 2 * PAD, rows + 2 * PAD, int(start.x) // CELL + PAD, int(start.y) // CELL + PAD
    )
    on, first, flips = (a[PAD : PAD + rows, PAD : PAD + cols] for a in (on, first, flips))

    # progress along the highway's in-frame length: its edges ignite as it leaves the blob and
    # fade again towards the frame
    road = (on == 1) & (first > HIGHWAY_FROM)
    f = (first - HIGHWAY_FROM) / (first[road].max() - HIGHWAY_FROM)
    heat = np.clip(np.minimum(f / 0.12, (1 - f) / 0.4), 0, 0.999)
    edge = 5 + (heat * 4).astype(np.int64)  # cells flipped once trace the highway's edges
    inside = np.where(f < 0.7, 3, 4)
    highway = np.where(flips == 1, edge, inside)
    blob = np.where(flips >= 4, 2, 1)
    grid = np.where(on == 1, np.where(first > HIGHWAY_FROM, highway, blob), 0)
    grid_runs(s, grid, PALETTE, CELL)

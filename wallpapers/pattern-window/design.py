"""A room in MacPaint-style 8x8 fill patterns: a tall window and the slanted patch of light it throws on the floor."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import binary_erosion

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_4,
    BG_ALT,
    UI,
    Canvas,
    P,
    Paint,
    Ref,
    Vec,
    design,
)
from walldye.field import cells, runs
from walldye.geom import Affine
from walldye.pixel import grid_runs

CELL = 3
TILE = 8 * CELL
WIN_W, WIN_H = 261, 528
SILL = 18  # sill overhang past the frame on each side, and its depth
FLOOR_GAP = 81  # window bottom to the floor line
BAR = 0.035  # frame and glazing-bar width, as a fraction of the window

# 1-bit 8x8 patterns in the Susan Kare vocabulary, from empty to solid.
PATTERNS = (
    ("........",) * 8,
    ("#.......", "........", "........", "........", "....#...", "........", "........", "........"),
    ("#.......", "........", "..#.....", "........", "....#...", "........", "......#.", "........"),
    ("#...#...", "........", "..#...#.", "........", "#...#...", "........", "..#...#.", "........"),
    ("#.#.#.#.", "........") * 4,
    ("#.#.#.#.", ".#.#.#.#") * 4,
    ("#.#.#.#.", "########") * 4,
    ("########",) * 8,
)  # fmt: skip

# Fill regions, indices into the palette built in draw. Panes and their patches of light come in
# three rows, top of the window first; on the floor that is the row furthest from the wall.
WALL, FLOOR, BASE, FRAME, RIM, GLASS, LIT = 1, 2, 3, 4, 5, 6, 9

type Grid = NDArray[np.float64]


def pane(u: Grid, v: Grid) -> NDArray[np.bool_]:
    """Glass in window coordinates (0..1 across and down): two columns and three rows of panes
    inside the frame and glazing bars."""
    inside = (u > BAR) & (u < 1 - BAR) & (v > BAR) & (v < 1 - BAR)
    return (
        inside
        & (np.abs(u - 0.5) > BAR / 2)
        & (np.abs(v - 1 / 3) > BAR / 2)
        & (np.abs(v - 2 / 3) > BAR / 2)
    )


def fill_pattern(s: Canvas, level: int, paint: Paint) -> Ref:
    """PATTERNS[level] as a tile of `paint` cells over an empty ground, anchored at the canvas
    origin like the cell grid, so every region shares one pattern phase."""
    d = P()
    for r, row in enumerate(PATTERNS[level]):
        for c0, c1 in runs(np.array([ch == "#" for ch in row])):
            d.rect(c0 * CELL, r * CELL, (c1 - c0) * CELL, CELL)
    with s.pattern(TILE, TILE) as tile:
        tile.fill(d, paint)
    return tile.ref


@design(aspects="any")
def draw(s: Canvas) -> None:
    # (window's left edge, floor line): left of center with the floor low on a landscape screen;
    # on a portrait one the floor sits just below the middle, deep enough for a longer patch
    x0, floor_y = s.pick(landscape=(0.2234, 0.7139), portrait=(0.136, 0.6), snap=CELL)
    # light patch: the window's bottom edge lands at a..a+u on the floor, its top edge along v
    a = Vec(x0 + WIN_W + SILL, floor_y + 8 * CELL)
    u = Vec(372, 0)
    v = Vec(300, 219) if s.landscape else Vec(150, 420)
    y1 = floor_y - FLOOR_GAP
    y0 = y1 - WIN_H
    x1 = x0 + WIN_W

    xs, ys = cells(s.inset(0), CELL)
    region = np.where(ys < floor_y, WALL, FLOOR)
    region[(ys >= floor_y) & (ys < floor_y + 2 * CELL)] = BASE
    sill = (xs >= x0 - SILL) & (xs < x1 + SILL) & (ys >= y1) & (ys < y1 + SILL)
    region[sill] = FRAME
    wu, wv = (xs - x0) / WIN_W, (ys - y0) / WIN_H
    window = (wu >= 0) & (wu <= 1) & (wv >= 0) & (wv <= 1)
    region[window] = FRAME
    glass = window & pane(wu, wv)
    region[glass] = (GLASS + (wv * 3).astype(int).clip(0, 2))[glass]

    # map each floor cell back through the patch parallelogram to the part of the window that lit it
    back = Affine(u.x, u.y, v.x, v.y, a.x, a.y).inverse()
    fu = back.a * xs + back.c * ys + back.e
    fv = 1 - (back.b * xs + back.d * ys + back.f)
    lit = (ys >= floor_y) & (fu >= 0) & (fu <= 1) & (fv >= 0) & (fv <= 1) & pane(fu, fv)
    region[lit] = (LIT + (fv * 3).astype(int).clip(0, 2))[lit]
    # a solid rim keeps the sparse near patches' outlines crisp
    region[lit & ~binary_erosion(lit)] = RIM

    palette: list[Paint | None] = [
        None,
        fill_pattern(s, 1, BG_ALT),
        fill_pattern(s, 2, BG_ALT),
        BG_ALT,
        UI,
        ACCENT_4,
        *(fill_pattern(s, level, ACCENT_2) for level in (5, 4, 3)),
        *(fill_pattern(s, level, ACCENT) for level in (6, 5, 4)),
    ]
    grid_runs(s, region, palette, CELL)

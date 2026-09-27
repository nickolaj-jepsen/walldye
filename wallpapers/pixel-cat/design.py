"""A cat seen from behind on a windowsill, watching the moon: pixel art with a Bayer-dithered halo."""

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_7,
    ACCENT_8,
    BG_ALT,
    BG_DEEP,
    BLACK,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    by_regime,
    design,
)
from walldye.pixel import Pixels

PX = 8
# Palette indices; 0 is the wall, which also stands in for the night sky so the frame carries
# the structure. On paper BLACK and BG_DEEP are lighter than the wall, so the cat and the
# shadow move toward the foreground, and the sill drops a UI step so the cat stands off it.
PALETTE = (
    None,
    by_regime(BG_DEEP, BG_ALT),
    ACCENT_8,
    ACCENT_7,
    UI,
    by_regime(UI_ALT, UI),
    by_regime(UI_HI, UI_ALT),
    by_regime(BLACK, MUTED),
    ACCENT_1,
    ACCENT,
)
SHADOW, HALO_OUT, HALO_IN, FRAME, SILL, SILL_TOP, FUR, RIM, MOON = range(1, 10)

# The scene in grid cells: the sill overhangs the frame by 4 cells a side, and its shadow ends
# 4 rows below the sill top.
COLS, ROWS = 72, 76
FX0, FX1 = 4, 68  # window outer frame; its top is row 0 and its foot stands on the sill
SILL_Y = 71
MID, TRANSOM = 35.5, 33.5  # centre lines of the 2-cell mullion and transom, in cell indices
MX, MY, MR = 51.5, 17.5, 8.5  # moon, in cell-centre units, centred in the upper-right pane
CAT_X = 14  # cat's left edge; it sits on the sill
STARS = ((10, 6), (24, 19), (16, 27), (28, 13), (61, 41), (30, 39), (14, 45), (56, 53))

CAT = """
...#..........#.............
...##........##.............
...###......###.............
...####....####.............
...############.............
..##############............
..##############............
..##############............
..##############............
...############.............
....###########.............
....###########.............
....###########.............
...############.............
...#############............
..##############............
..###############...........
.################...........
.#################..........
.#################..........
.#################......##..
.##################......##.
.##################.......##
.##################.......##
..#################.......##
..##################.....##.
...#######################..
....#################.......
"""

# Maria as cell offsets from the moon's centre cell: two blobs inside, one breaking the limb.
MARIA = (
    (-5, -4),
    (-4, -4),
    (-3, -4),
    (-6, -3),
    (-5, -3),
    (-4, -3),
    (-5, -2),
    (5, 1),
    (6, 1),
    (7, 1),
    (8, 1),
    (6, 2),
    (7, 2),
    (8, 2),
    (7, 3),
    (-1, 4),
    (0, 4),
    (1, 4),
    (-2, 5),
    (-1, 5),
    (0, 5),
    (-1, 6),
)


def cat() -> NDArray[np.int64]:
    """The cat as palette indices, 0 where transparent: a FUR silhouette with a continuous RIM
    on the edges facing the moon, and MOON on the ear tips and the crown between them."""
    m = np.array([[ch == "#" for ch in r] for r in CAT.strip().split("\n")])
    h, w = m.shape
    pad = np.pad(m, 1)
    up, rt = ~pad[:-2, 1:-1], ~pad[1:-1, 2:]
    cols = np.arange(w)[None, :]
    rows = np.arange(h)[:, None]
    rim = m & (rt | up & (cols >= 7))
    rim[20:, 20:] = m[20:, 20:] & (up | rt)[20:, 20:] & (rows[20:] < 24)  # tail: upper edge only
    # Close diagonal steps with the inner corner cell so the rim reads as one line, not dotted
    # singletons.
    for y, x in zip(*np.nonzero(rim.copy()), strict=True):
        for dx in (1, -1):
            if (
                0 <= x + dx < w
                and y + 1 < h
                and rim[y + 1, x + dx]
                and not (rim[y, x + dx] or rim[y + 1, x])
            ):
                if m[y + 1, x]:
                    rim[y + 1, x] = True
                elif m[y, x + dx]:
                    rim[y, x + dx] = True
    g = np.where(m, FUR, 0)
    g[rim] = RIM
    g[0:2, 14] = g[0, 3] = MOON  # ear tips
    g[4, 7:11] = MOON  # crown between the ears
    return g


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of centre on a landscape screen, in the upper half of a portrait one; snapped so
    # the grid origin is a whole cell
    c = s.pick(landscape=(0.62, 0.52), portrait=(0.55, 0.4), snap=PX)
    px = Pixels(COLS, ROWS, PALETTE)
    ys, xs = np.mgrid[0:ROWS, 0:COLS]
    pane = (xs >= FX0) & (xs < FX1) & (ys < SILL_Y)

    # A tight two-band halo whose bands meet in 2-cell checkers.
    d = np.hypot(xs + 0.5 - MX, ys + 0.5 - MY)
    q = np.clip((12.5 - d) / 2, 0, 2)
    q = np.floor(q) + np.clip((q - np.floor(q) - 0.5) * 8 + 0.5, 0, 1)
    px.dither(q / 2, (0, HALO_OUT, HALO_IN), method="bayer", matrix=2, where=pane)
    for x, y in STARS:
        px.grid[y, x] = FRAME

    px.grid[d <= MR] = MOON
    for dx, dy in MARIA:
        px.grid[int(MY) + dy, int(MX) + dx] = RIM

    # Frame, mullion, transom, sill and the sill's shadow on the wall.
    frame = pane & ~((xs >= FX0 + 2) & (xs < FX1 - 2) & (ys >= 2))
    frame |= pane & ((abs(xs - MID) < 1) | (abs(ys - TRANSOM) < 1))
    px.grid[frame] = FRAME
    px.grid[SILL_Y] = SILL_TOP
    px.grid[SILL_Y + 1 : SILL_Y + 3] = SILL
    px.grid[SILL_Y + 3] = SHADOW
    px.grid[SILL_Y + 4, 2:-2] = SHADOW

    g = cat()
    sub = px.grid[SILL_Y - g.shape[0] : SILL_Y, CAT_X : CAT_X + g.shape[1]]
    sub[g > 0] = g[g > 0]
    px.draw(s, PX, c - (COLS // 2 * PX, ROWS // 2 * PX))

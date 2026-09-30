"""A Game of Life soup reduced to still lifes and blinkers, with one glider."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import binary_dilation, label

from walldye import (
    ACCENT,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    BG_ALT,
    UI,
    Canvas,
    NpRng,
    P,
    Path,
    Vec,
    design,
)

CELL, SQ, RAD = 14, 11, 2  # grid pitch, square side, corner radius
INSET = (CELL - SQ) / 2
# The soup runs on a fixed field, so every screen shape gets the same ash.
COLS, ROWS = 137, 77
PAD = 120  # dead margin so escaping gliders die far from the soup
SOUP = (42, 46, 40, 26)  # ellipse center and radii, in cells
GENS = 1500
LINK = 2  # cells; debris further than 2 * LINK from the main island is dropped
# (col, row) cells of the glider in the phase that travels up and to the right
GLIDER = np.array(
    [(x, y) for y, row in enumerate(("OOO", "..O", ".O.")) for x, c in enumerate(row) if c == "O"]
)
# The glider, then ghosts three periods (12 generations, 3 cells) apart, so each echo stands clear.
TRAIL = (ACCENT, ACCENT_5, ACCENT_6, ACCENT_7)


def life(g: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """One Game of Life generation of `g`; cells beyond its edge stay dead."""
    p = np.pad(g, 1).astype(np.uint8)
    h, w = g.shape
    n = np.zeros((h, w), np.uint8)
    for dy in range(3):
        for dx in range(3):
            if dy != 1 or dx != 1:
                n += p[dy : dy + h, dx : dx + w]
    return (n == 3) | (g & (n == 2))


def ash(rng: NpRng) -> NDArray[np.intp]:
    """The settled soup's largest island as (col, row) cells about its bounding-box center."""
    g = np.zeros((ROWS + 2 * PAD, COLS + 2 * PAD), bool)
    yy, xx = np.mgrid[:ROWS, :COLS]
    r = ((xx - SOUP[0]) / SOUP[2]) ** 2 + ((yy - SOUP[1]) / SOUP[3]) ** 2
    g[PAD : PAD + ROWS, PAD : PAD + COLS] = (r < 1) & (rng.random((ROWS, COLS)) < 0.4)
    for _ in range(GENS):
        g = life(g)
    g &= life(life(g))  # keep only still lifes and blinkers
    g = g[PAD : PAD + ROWS, PAD : PAD + COLS] & (r < 1.1)
    lab, _ = label(g, np.ones((3, 3), bool))
    g &= np.bincount(lab.ravel())[lab] >= 3  # lone cells cut from passing gliders
    # keep one island: the largest group of objects within 2 * LINK cells of each other
    near, _ = label(binary_dilation(g, np.ones((2 * LINK + 1,) * 2, bool)))
    sizes = np.bincount(near.ravel(), weights=g.ravel())
    sizes[0] = 0
    ys, xs = np.nonzero(g & (near == sizes.argmax()))
    return np.column_stack((xs - (xs.min() + xs.max()) // 2, ys - (ys.min() + ys.max()) // 2))


def squares(cells: NDArray[np.intp], at: Vec) -> Path:
    """A rounded square centered in each (col, row) cell of the grid whose cell (0, 0) starts at `at`."""
    d = P()
    for col, row in cells:
        d.rrect(at.x + col * CELL + INSET, at.y + row * CELL + INSET, SQ, SQ, RAD)
    return d


@design(aspects="any")
def draw(s: Canvas) -> None:
    with s.pattern(CELL, CELL) as board:
        board.fill(P().circle((CELL / 2, CELL / 2), 0.9), BG_ALT)
    s.fill(P().rect(0, 0, s.w, s.h), board.ref)
    # cell corners on the board's grid: the island low on the left, the glider up to its right
    island = s.pick(landscape=(0.299, 0.609), portrait=(0.44, 0.64), snap=CELL)
    glider = s.pick(landscape=(0.766, 0.363), portrait=(0.72, 0.29), snap=CELL)
    s.fill(squares(ash(s.np_rng(29)), island), UI)
    for k, tone in enumerate(TRAIL):
        s.fill(squares(GLIDER, glider + (-3 * k * CELL, 3 * k * CELL)), tone)

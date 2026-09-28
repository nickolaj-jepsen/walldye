"""Fixture: v1 pixel helpers with positional origins, callbacks and the dropped constants."""

import numpy as np
from wallgen import ACCENT, BG, GREYS, SHADES, UI, UI_HI, bayer, dither, glyphs, grid_runs, sprite

COLS, ROWS, CELL = 64, 36, 6
ART = """
.##.
####
.##.
"""


def draw(s):
    ys, xs = np.mgrid[0:ROWS, 0:COLS]
    tone = np.clip(xs / COLS * 0.8 + 0.1 * np.sin(ys / 3), 0, 1)
    grid = np.array(dither(lambda i, j: tone[j, i] * 0.9, COLS, ROWS, 3, "bayer", matrix=4))
    grid_runs(s, grid.tolist(), [BG, UI, ACCENT], CELL, 12, 30)
    m = bayer(4)
    speck = dither(lambda i, j: m[j % 4][i % 4], 8, 8, 2, "bluenoise", seed=3)
    grid_runs(s, speck, [None, UI_HI], 4, ox=1500, oy=40, skip=0)
    glyphs(s, ["LEVEL " + SHADES], UI_HI, "5x8", 2, 100, 900)
    glyphs(s, ["HP"], lambda c, r, ch: ACCENT if ch == "H" else UI, font="5x8", px=3, y=940)
    sprite(s, ART, {"#": GREYS[5]}, 4, 1700, 900)

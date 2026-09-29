"""A total solar eclipse as terminal art: corona brightness picks each cell's character from a hand-made 5x7 glyph ramp, and at-signs trace the limb."""

import math

import numpy as np
from scipy.ndimage import binary_dilation

from walldye import ACCENT, ACCENT_2, ACCENT_4, ACCENT_6, Canvas, clamp, design
from walldye.field import falloff, gauss
from walldye.pixel import grid_runs, threshold_matrix

PX, CW, CH = 2, 6, 10  # glyph pixel size; cell in glyph pixels (a 5x7 glyph plus gutter)
CELL_X, CELL_Y = CW * PX, CH * PX
R = 256  # disc radius
TILT = 0.32  # equator tilt on a landscape screen, radians
PORTRAIT_TILT = TILT + math.pi / 2  # a portrait screen turns the equator along its long side
REACH = 732  # room the longest streamer needs beyond the center

# . - = + * # @, sparse to dense; '@' is kept for the limb ring
GLYPHS = [
    ".....|.....|.....|.....|.....|.....|.....",
    ".....|.....|.....|.....|.....|..#..|.....",
    ".....|.....|.....|.###.|.....|.....|.....",
    ".....|.....|#####|.....|#####|.....|.....",
    ".....|..#..|..#..|#####|..#..|..#..|.....",
    ".....|..#..|#.#.#|.###.|#.#.#|..#..|.....",
    ".#.#.|#####|.#.#.|.#.#.|#####|.#.#.|.....",
    ".###.|#...#|#.###|#.#.#|#.##.|#....|.###.",
]
BITS = np.array([[[c == "#" for c in row] for row in g.split("|")] for g in GLYPHS])
TONE = np.array([0, 1, 1, 2, 2, 3, 3, 4])  # palette index per glyph level
PALETTE = (None, ACCENT_6, ACCENT_4, ACCENT_2, ACCENT)
# (angle from the equator, peak, base width px, length px)
STREAMERS = [
    (0.0, 1.0, 42, 470),
    (math.pi + 0.04, 0.95, 40, 440),
    (0.2, 0.7, 24, 250),
    (math.pi - 0.2, 0.7, 24, 230),
    (-math.pi / 2 - 0.1, 0.65, 22, 210),
]


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = s.w // CELL_X, s.h // CELL_Y
    # right of center on a landscape screen, pulled in where the long streamer would reach the
    # edge; mid-height on a portrait one, where both streamers run along the long side
    c = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.47))
    cx = min(c.x, s.w - REACH) if s.landscape else c.x
    # on a cell corner, so the limb ring comes out symmetric
    cx, cy = round(cx / CELL_X) * CELL_X, round(c.y / CELL_Y) * CELL_Y
    tilt = TILT if s.landscape else PORTRAIT_TILT

    dx = (np.arange(cols) + 0.5) * CELL_X - cx
    dy = (np.arange(rows)[:, None] + 0.5) * CELL_Y - cy
    r, a = np.hypot(dx, dy), np.arctan2(dy, dx)
    h = np.maximum(r - R, 0)  # height above the limb

    # smooth radial corona, cut off well inside the frame so the far field stays empty
    val = (0.8 * np.exp(-h / 40) + 0.15 * np.exp(-h / 100)) * (r < 2.2 * R)
    for off, peak, width, length in STREAMERS:
        da = (a - tilt - off + np.pi) % (2 * np.pi) - np.pi
        taper = falloff(h, length)
        val += (
            peak
            * gauss(r * np.sin(da) / (width * (0.6 + 0.4 * taper)), 1)  # narrows as it tapers
            * (np.cos(da) > 0)
            * taper**0.8
            * clamp(h / 50)
        )

    # a light threshold-matrix nudge softens level boundaries without clumping
    tm = threshold_matrix("bluenoise", 64, s.np_rng(7))
    tm = np.tile(tm, (-(-rows // 64), -(-cols // 64)))[:rows, :cols]
    level = np.clip(val * 6.4 + (tm - 0.5) * 0.7, 0, 6).astype(int)
    disc = r < R
    level[disc] = 0
    level[binary_dilation(disc) & ~disc] = 7  # a one-cell limb, whatever the cell aspect

    # stamp each cell's glyph, inked in its level's tone, into a grid of glyph pixels
    pix = np.zeros((rows, CH, cols, CW), int)
    pix[:, 1:8, :, :5] = (BITS[level] * TONE[level][..., None, None]).transpose(0, 2, 1, 3)
    grid_runs(s, pix.reshape(rows * CH, cols * CW), PALETTE, PX)

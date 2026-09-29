"""Spectrogram of a whistled tune cut off at a playhead, with dithered falloff."""

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_6,
    ACCENT_7,
    BG_ALT,
    UI,
    UI_HI,
    Canvas,
    design,
)
from walldye.pixel import Pixels, blue_noise

type Field = NDArray[np.float64]

CELL, ROWS, MARGIN = 3, 126, 96  # pixel cell; frequency rows (378 units); panel's left margin
SPAN = 1920  # canvas units per unit of time: the 16:9 panel shows t = 0.05 .. NOW
NOW = 1299 / 1920  # time at the playhead
SUB = 5  # time samples per column, so a steep sweep fills every row it crosses
CAP = """
#######
.#####.
..###..
...#...
"""
# Phrases of (time, pitch) knots; pitch in rows above the band floor. Gaps between phrases are
# breaths. The first two only show on screens wider than 16:9, where more of the past fits.
PHRASES = [
    [(-0.60, 22), (-0.56, 19), (-0.52, 25), (-0.47, 31), (-0.43, 29), (-0.38, 24), (-0.34, 18)],
    [(-0.29, 17), (-0.25, 21), (-0.21, 27), (-0.16, 24), (-0.12, 30), (-0.07, 28), (0.02, 19)],
    [(0.07, 18), (0.11, 21), (0.15, 28), (0.20, 25), (0.24, 33), (0.29, 31), (0.33, 20)],
    [(0.37, 17), (0.41, 23), (0.45, 20), (0.49, 28), (0.53, 26)],
    [(0.57, 19), (0.61, 26), (0.66, 34), (0.74, 31)],  # still sounding when the capture stops
]
# Palette indices: 1 is the noise floor, 2-5 the accent ramp by strength, 6-7 the playhead.
PALETTE = [None, BG_ALT, ACCENT_7, ACCENT_6, ACCENT_4, ACCENT, UI, UI_HI]
# Per harmonic: (core half-width in rows, falloff width in rows, core index, falloff index).
BANDS = [(1.5, 2.5, 5, 4), (1.0, 2.0, 4, 3), (0.8, 1.6, 3, 2)]
# Fraction of a phrase spent swelling and fading, and the vibrato depth in rows.
RISE, FADE, VIBRATO = 0.06, 0.18, 0.25


def melody(t: Field) -> tuple[Field, Field]:
    """The pitch in rows and the loudness in [0, 1] of the tune at times `t`, any shape;
    loudness is 0 between phrases."""
    f0, amp = np.zeros(t.shape), np.zeros(t.shape)
    for knots in PHRASES:
        kt, kp = zip(*knots, strict=True)
        on = (t >= kt[0]) & (t <= kt[-1])
        pitch = CubicSpline(kt, kp, bc_type="clamped")(t) + VIBRATO * np.sin(t * 420)
        f0 = np.where(on, pitch, f0)
        u = np.clip((t - kt[0]) / (kt[-1] - kt[0]), 0, 1)
        amp = np.where(on, np.minimum(1, u / RISE) * np.minimum(1, (1 - u) / FADE) ** 0.7, amp)
    return f0, amp


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the playhead's top, two thirds across with the future open to its right; a narrower
    # screen shows less of the past, and a portrait one holds the panel in its upper third
    head = s.pick(landscape=(NOW, 312 / 1080), portrait=(NOW, 0.3), snap=CELL)
    cols = round(head.x - MARGIN) // CELL  # panel columns; the playhead is the next one
    # (SUB, cols) sample times across each column; only the past, up to the playhead, is drawn
    x = MARGIN + (np.arange(cols) + (np.arange(SUB)[:, None] + 0.5) / SUB) * CELL
    f0, amp = melody(NOW + (x - head.x) / SPAN)
    on = amp > 0
    track = (np.where(on, f0, np.inf).min(axis=0), np.where(on, f0, -np.inf).max(axis=0))
    level = amp[SUB // 2]  # loudness at the column center
    f = np.arange(ROWS)[::-1][:, None] + 0.5  # row 0 is the top (high frequency)

    thr = np.tile(blue_noise(64, s.np_rng(5)), (ROWS // 64 + 1, cols // 64 + 1))[:ROWS, :cols]
    px = Pixels(cols + 4, ROWS + 4, PALETTE)  # spare rows above and columns right for the cap
    grid = px.grid[4:, :cols]
    grid[thr < 0.05] = 1  # noise floor: sparse specks, ~5% coverage

    # stroke thickness follows the note envelope; dither only in the thin falloff
    live = level > 0.02
    for h, (core, fall, ci, fi) in enumerate(BANDS, start=1):
        d = np.maximum(np.maximum(h * track[0] - f, f - h * track[1]), 0) - core * level
        halo = live & (d > 0) & (thr < np.exp(-((d / fall) ** 2)) * level * 0.7)
        grid[halo & (grid < fi)] = fi
        body = live & (d <= 0) & (level * core > 0.35)
        grid[body] = np.maximum(grid[body], ci)

    px.grid[4:, cols] = 6
    px.stamp(CAP, cols - 3, 0, {"#": 7})
    px.draw(s, CELL, (MARGIN, head.y - 4 * CELL))

"""After donut.c: a torus frozen mid-spin, z-buffered onto a character grid and shaded with a twelve-step ASCII luminance ramp."""

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_4,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    by_regime,
    design,
    mix,
)
from walldye.pixel import glyphs

type Vec3 = NDArray[np.float64]

RAMP = ".,-~:;=!*#$@"  # donut.c's ramp, darkest to brightest
# One tone per ramp step: two quiet bands, then UI_HI and three accent-ladder steps on top.
# Thin glyph strokes read fainter on a light ground, so light themes lift the two bands, and
# the first accent step, which ACCENT_4 would leave paler than the UI_HI step below it.
LOW, MID = by_regime(UI, UI_ALT), by_regime(UI_ALT, mix(UI_ALT, UI_HI, 0.5))
WARM = by_regime(ACCENT_4, ACCENT_2)
TONES: tuple[Colour, ...] = (LOW,) * 4 + (MID,) * 4 + (UI_HI, WARM, ACCENT_1, ACCENT)
CW, CH = 8, 16  # 8x16 font at px=1
COLS, ROWS = 120, 60  # scratch grid, trimmed to the torus before it is placed
TILT = 0.65  # radians about x, tipping the near rim towards the viewer
K = 600  # projection scale in px
SAMPLES = (500, 1400)  # around the tube, around the ring


def unit(v: tuple[float, float, float]) -> Vec3:
    """`v` scaled to length 1."""
    a = np.asarray(v, dtype=float)
    return a / np.linalg.norm(a)


LIGHT = unit((-0.55, 0.6, -0.6))
GLINT = unit((-0.6, 0.5, -0.62))  # highlight direction, aimed at the upper-left outer rim


@design(aspects="any")
def draw(s: Canvas) -> None:
    th, ph = np.meshgrid(
        np.linspace(0, 2 * np.pi, SAMPLES[0], endpoint=False),
        np.linspace(0, 2 * np.pi, SAMPLES[1], endpoint=False),
    )
    # torus around the z axis: tube radius 1, ring radius 2; the viewer looks down +z
    nx, ny, nz = np.cos(th) * np.cos(ph), np.cos(th) * np.sin(ph), np.sin(th)
    x, y, z = 2 * np.cos(ph) + nx, 2 * np.sin(ph) + ny, nz
    ca, sa = np.cos(TILT), np.sin(TILT)
    y, z = y * ca - z * sa, y * sa + z * ca
    ny, nz = ny * ca - nz * sa, ny * sa + nz * ca
    ooz = 1 / (z + 7)
    i = ((COLS * CW / 2 + K * ooz * x) // CW).astype(int)
    j = ((ROWS * CH / 2 - K * ooz * y) // CH).astype(int)
    normal = np.stack([nx, ny, nz], axis=-1)
    diffuse = np.clip(normal @ LIGHT, 0, 1)
    spec = np.clip(normal @ GLINT, 0, 1) ** 10 * (np.cos(th) > 0)  # outer rim only
    lum = 0.62 * diffuse**1.3 + 0.5 * spec
    lvl = np.where(diffuse < 0.1, -1, np.minimum((lum * len(RAMP)).astype(int), len(RAMP) - 1))

    ok = (i >= 0) & (i < COLS) & (j >= 0) & (j < ROWS)
    i, j, ooz, lvl = i[ok], j[ok], ooz[ok], lvl[ok]
    out = np.full((ROWS, COLS), -1)
    order = np.argsort(ooz)  # far to near, so nearer samples overwrite
    out[j[order], i[order]] = lvl[order]
    # drop stray cells at the silhouette tips: fewer than three lit cells in their 3x3 block
    nb = ndimage.convolve((out >= 0).astype(int), np.ones((3, 3), int), mode="constant")
    out[nb < 3] = -1
    rows, cols = np.nonzero(out >= 0)
    out = out[rows.min() : rows.max() + 1, cols.min() : cols.max() + 1]
    lines = ["".join(RAMP[v] if v >= 0 else " " for v in row) for row in out.tolist()]

    # right of centre on a landscape screen, the upper half of a portrait one
    c = s.pick(landscape=(0.646, 0.5), portrait=(0.5, 0.42), snap=1)
    at = (c.x - out.shape[1] * CW // 2, c.y - out.shape[0] * CH // 2)
    glyphs(s, lines, lambda col, row, ch: TONES[RAMP.index(ch)], at=at, font="8x16", px=1)

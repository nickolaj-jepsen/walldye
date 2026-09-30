"""A torus at a three-quarter tilt, drawn on a character grid with an ASCII luminance ramp."""

import math

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
    Color,
    Params,
    by_regime,
    design,
    knob,
    mix,
)
from walldye.pixel import glyphs

type Vec3 = NDArray[np.float64]


class Donut(Params):
    a: float = knob(
        default=-52, lo=-90, hi=90, unit="deg", doc="donut.c's A: tilt about the screen's x axis"
    )
    b: float = knob(
        default=-20, lo=-90, hi=90, unit="deg", doc="donut.c's B: turn about the view axis"
    )


RAMP = ".`-:;+=*o%#@"  # darkest to brightest
# One tone per ramp step: two quiet bands, then UI_HI and three accent-ladder steps on top.
# Thin glyph strokes read fainter on a light ground, so light themes lift the two bands, and
# the first accent step, which ACCENT_4 would leave paler than the UI_HI step below it.
LOW, MID = by_regime(UI, UI_ALT), by_regime(UI_ALT, mix(UI_ALT, UI_HI, 0.5))
WARM = by_regime(ACCENT_4, ACCENT_2)
TONES: tuple[Color, ...] = (LOW,) * 4 + (MID,) * 4 + (UI_HI, WARM, ACCENT_1, ACCENT)
CW, CH = 8, 16  # 8x16 font at px=1
COLS, ROWS = 120, 60  # scratch grid, trimmed to the torus before it is placed
R1, R2 = 1, 2  # tube and ring radius
K1, K2 = 600, 7  # projection scale in px, and the viewer's distance
SAMPLES = (500, 1400)  # around the tube, around the ring


def unit(v: tuple[float, float, float]) -> Vec3:
    """`v` scaled to length 1."""
    a = np.asarray(v, dtype=float)
    return a / np.linalg.norm(a)


def rotate(v: Vec3, a: float, b: float) -> Vec3:
    """Rows of `v` turned by `a` radians about x, then `b` about z, as donut.c turns its torus."""
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    rx = np.array([[1, 0, 0], [0, ca, sa], [0, -sa, ca]])
    rz = np.array([[cb, sb, 0], [-sb, cb, 0], [0, 0, 1]])
    return v @ rx @ rz


LIGHT = unit((-0.4, 0.45, -0.8))  # from the upper left, in front
GLINT = unit((-0.6, 0.5, -0.62))  # highlight direction, aimed at the upper-left outer rim


@design(aspects="any")
def draw(s: Canvas[Donut]) -> None:
    th, ph = np.meshgrid(
        np.linspace(0, 2 * np.pi, SAMPLES[0], endpoint=False),
        np.linspace(0, 2 * np.pi, SAMPLES[1], endpoint=False),
    )
    # donut.c's torus: a circle in the xy plane swept round the y axis; the viewer looks down +z
    ring = R2 + R1 * np.cos(th)
    pts = np.stack([ring * np.cos(ph), R1 * np.sin(th), ring * np.sin(ph)], axis=-1)
    normal = np.stack([np.cos(th) * np.cos(ph), np.sin(th), np.cos(th) * np.sin(ph)], axis=-1)
    a, b = math.radians(s.params.a), math.radians(s.params.b)
    pts, normal = rotate(pts, a, b), rotate(normal, a, b)
    x, y, z = pts[..., 0], pts[..., 1], pts[..., 2]
    ooz = 1 / (z + K2)
    i = ((COLS * CW / 2 + K1 * ooz * x) // CW).astype(int)
    j = ((ROWS * CH / 2 - K1 * ooz * y) // CH).astype(int)
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

    # right of center on a landscape screen, the upper half of a portrait one
    c = s.pick(landscape=(0.646, 0.5), portrait=(0.5, 0.42), snap=1)
    at = (c.x - out.shape[1] * CW // 2, c.y - out.shape[0] * CH // 2)
    glyphs(s, lines, lambda col, row, ch: TONES[RAMP.index(ch)], at=at, font="8x16", px=1)

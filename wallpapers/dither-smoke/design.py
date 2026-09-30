"""An incense plume in Sierra Lite error-diffusion dither."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import convolve, gaussian_filter

from walldye import ACCENT, ACCENT_3, ACCENT_5, UI, UI_ALT, Canvas, P, Vec, design
from walldye.field import noise_grid
from walldye.geom import Affine, spline_points
from walldye.pixel import blue_noise, dither, grid_runs

type Pts = NDArray[np.float64]

CELL = 2
# The plume is laid out in its own 1920x1080 frame with the ember at EMBER, then moved onto
# the canvas as one piece, so every screen shape gets the same plume.
FRAME = (1920, 1080)
EMBER = Vec(600, 958)
# Strand centerlines in frame units: the stem, a wisp that breaks off right and curls, the main
# rise bending left, and a thinner branch across it.
STEM = (
    (600, 958),
    (601, 880),
    (600, 820),
    (594, 760),
    (610, 700),
    (628, 640),
    (616, 580),
    (598, 520),
    (608, 468),
    (632, 432),
)
WISP = ((632, 432), (672, 408), (722, 400), (764, 414))
RISE = ((632, 432), (628, 370), (602, 300), (560, 240), (498, 190), (420, 152), (340, 132))
BRANCH = ((604, 300), (650, 250), (712, 214), (790, 196))
# Palette index per (height zone, dither level): lit accent cells over the ember, the darker
# accent ramp up the column, then UI and UI_ALT in the veils.
PALETTE = (None, ACCENT, ACCENT_3, ACCENT_5, UI, UI_ALT)
TONE = np.array([[0, 2, 1], [0, 3, 2], [0, 4, 5]])


def curl(path: Pts, c: tuple[float, float], turns: float, shrink: float, sign: int) -> Pts:
    """`path` continued from its last point into an inward spiral about `c`: `turns` turns
    (clockwise on screen for sign 1, anticlockwise for -1), the radius easing down to `shrink`
    times its starting length."""
    center = np.asarray(c, dtype=np.float64)
    p = path[-1] - center
    r0, a0 = np.hypot(p[0], p[1]), np.arctan2(p[1], p[0])
    t = np.linspace(0, 1, int(260 * turns))[1:]
    a = a0 + sign * t * turns * 2 * np.pi
    r = r0 * (1 - (1 - shrink) * t**0.8)
    return np.vstack([path, center + np.c_[np.cos(a), np.sin(a)] * r[:, None]])


@design(aspects="any")
def draw(s: Canvas) -> None:
    # a portrait screen gets the same plume half as large again, drawn on 3-unit cells
    cell = CELL if s.landscape else 3
    zoom = cell / CELL
    # left third on a landscape screen with the ember near the bottom edge; low and central
    # on a portrait one, so the plume climbs through the upper half
    ember = s.pick(landscape=(0.3125, EMBER.y / FRAME[1]), portrait=(0.5, 0.84), snap=cell)
    cols, rows = FRAME[0] // CELL, FRAME[1] // CELL
    strands = [
        (spline_points(STEM, 60), 1.0, 5),
        (curl(spline_points(WISP, 60), (738, 348), 1.4, 0.3, -1), 0.85, 4),
        (spline_points(RISE, 60), 0.8, 18),
        (spline_points(BRANCH, 60), 0.55, 12),
    ]

    dens = np.zeros((rows, cols))
    wob = noise_grid(1024, 640, 64, s.np_rng(21), octaves=2)
    wx, wy = (noise_grid(1024, 640, 32, s.np_rng(k), octaves=2) for k in (31, 32))
    rng = s.np_rng(4)
    for path, amp, fan in strands:
        d = np.gradient(path, axis=0)
        normal = np.c_[-d[:, 1], d[:, 0]] / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-6)[:, None]
        rise = np.clip((EMBER.y - path[:, 1]) / 800, 0, 1)
        for k in range(5):
            # filaments braid inside the ribbon: offsets drift with noise and widen with height
            o = (k - 2) * (0.6 + 3 * rise + fan * rise**2) + 10 * rise * np.sin(
                np.arange(len(path)) / (40 + 9 * k) + rng.uniform(0, 6)
            )
            q = (path + normal * o[:, None]) / CELL
            # domain warp that grows with height, so the veils fray instead of staying clean tendrils
            qi = np.clip(q[:, 0].astype(int), 0, cols - 1)
            qj = np.clip(q[:, 1].astype(int), 0, rows - 1)
            q += np.c_[wx[qj, qi], wy[qj, qi]] * (14 * rise[:, None] ** 2.2)
            i = np.clip(q[:, 0].astype(int), 0, cols - 1)
            j = np.clip(q[:, 1].astype(int), 0, rows - 1)
            np.add.at(dens, (j, i), amp * (0.6 + 0.4 * wob[j, i]) * (1 - 0.3 * rise))
    dens = gaussian_filter(dens, 1.0)

    # height above the ember, per cell row
    above = EMBER.y - np.arange(rows)[:, None] * CELL
    # thin and part-dithered just above the ember, with a small gap so the ember reads on its
    # own, and dissipating into nothing at the plume's top
    v = (
        np.clip(dens / 0.9, 0, 1)
        * np.clip((908 - above) / 110, 0, 1)
        * np.clip((above - 8) / 16, 0, 1)
        * np.clip(0.62 + above / 400, 0, 1)
    )
    grid = dither(v, 3, method="sierra-lite", serpentine=True)
    # drop orphan cells so the thin veils stay coherent ribbons
    lit = (grid > 0).astype(int)
    grid[(grid > 0) & (convolve(lit, np.ones((3, 3), dtype=int), mode="constant") <= 2)] = 0

    # the plume cools with height: accent over the ember, the darker ramp up the column, UI
    # in the veils; void-and-cluster jitter dithers the zone boundaries too
    bn = blue_noise(64, s.np_rng(3))
    jit = np.tile(bn, (rows // 64 + 1, cols // 64 + 1))[:rows, :cols] - 0.5
    h = above + jit * 90
    zone = np.where(h < 150, 0, np.where(h < 470, 1, 2))
    origin = ember - EMBER * zoom
    grid_runs(s, TONE[zone, grid], PALETTE, cell, origin)

    # in frame units: the stick below the ember as a stair-stepped line one cell wide, stepping
    # left every six cells, then the ember itself
    ex, ey = EMBER
    stick = P()
    for n in range(0, 40, 6):
        stick.rect(ex - 4 - n // 3, ey + 6 + 2 * n, CELL, 2 * min(6, 40 - n))
    with s.group(transform=Affine.frame(origin, deg=0, scale=zoom)):
        s.fill(stick, UI_ALT)
        s.fill(P().rect(ex - 5, ey - 5, 10, 10), ACCENT_3)
        s.fill(P().rect(ex - 3, ey - 3, 6, 6), ACCENT)

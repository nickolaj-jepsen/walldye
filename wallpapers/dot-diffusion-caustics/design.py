"""Pool-floor caustics from a Perlin wave surface, halftoned with Knuth's dot diffusion."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter, label

from walldye import ACCENT, ACCENT_3, ACCENT_6, UI, UI_ALT, Canvas, design
from walldye.field import Noise, cells, gauss
from walldye.pixel import bayer, grid_runs

type Field = NDArray[np.float64]

CELL = 3  # one photon per unit, so nine per cell
PAD = 240  # simulate beyond the frame so filaments enter from outside
# Wave octaves (size in units, lattice turn in degrees, weight), each on its own turned lattice
# so the net has no grain along the screen edges.
WAVES = ((260, 20, 1.0), (130, -41, 0.3))
LENS = 7885  # photon shift per unit of surface slope; higher folds the net into crumpled cusps
ANCHOR = (2937, 927)  # pool coordinates where the knot search starts, whatever the screen shape
SEARCH = 70  # cells either way from the anchor to look for the brightest junction
# Knuth 1987 class matrix: pixels are settled in this order within each 8x8 tile.
CLASS = np.array(
    [
        [34, 48, 40, 32, 29, 15, 23, 31],
        [42, 58, 56, 53, 21, 5, 7, 10],
        [50, 62, 61, 45, 13, 1, 2, 18],
        [38, 46, 54, 37, 25, 17, 9, 26],
        [28, 14, 22, 30, 35, 49, 41, 33],
        [20, 4, 6, 11, 43, 59, 57, 52],
        [12, 0, 3, 19, 51, 63, 60, 44],
        [24, 16, 8, 27, 39, 47, 55, 36],
    ]
)
NEIGHBORS = [
    (dy, dx, 2 if dy == 0 or dx == 0 else 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx
]


def dot_diffusion(v: Field, levels: int) -> NDArray[np.int64]:
    """Quantize `v` ((rows, cols) in [0, 1]) to 0 .. levels - 1, settling cells in CLASS order;
    each passes its error only to neighbors of a later class, edge neighbors twice as much."""
    rows, cols = v.shape
    n = levels - 1
    buf = np.pad(v * n, 1)
    cls = np.pad(
        CLASS[np.arange(rows)[:, None] % 8, np.arange(cols)[None, :] % 8], 1, constant_values=-1
    )
    out = np.zeros((rows, cols), np.int64)
    for k in range(64):
        ys, xs = np.nonzero(cls == k)
        old = buf[ys, xs]
        new = np.clip(np.round(old), 0, n)
        out[ys - 1, xs - 1] = new
        err = old - new
        wsum = np.zeros(len(ys))
        for dy, dx, w in NEIGHBORS:
            wsum += w * (cls[ys + dy, xs + dx] > k)
        wsum[wsum == 0] = 1  # "barons" with no later neighbor drop their error
        for dy, dx, w in NEIGHBORS:
            ok = cls[ys + dy, xs + dx] > k
            buf[ys[ok] + dy, xs[ok] + dx] += err[ok] * w / wsum[ok]
    return out


def surface(noise: Noise, x: NDArray[np.floating], y: NDArray[np.floating]) -> Field:
    """Water height at pool coordinates (x, y), the WAVES octaves summed; x and y broadcast."""
    h = np.zeros(np.broadcast_shapes(x.shape, y.shape))
    for size, deg, weight in WAVES:
        ca, sa = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        h += weight * noise((x * ca + y * sa) / size, (y * ca - x * sa) / size)
    return h


def caustics(noise: Noise, x0: float, y0: float, cols: int, rows: int) -> Field:
    """Photon density on the pool floor over `cols` x `rows` cells whose top-left corner is at
    pool coordinates (x0, y0): one photon per unit, shifted along the surface slope, so the
    mean is about 1 per cell."""
    x = x0 + np.arange(cols * CELL) + 0.5
    y = y0 + np.arange(rows * CELL) + 0.5
    gy, gx = np.gradient(surface(noise, x[None, :], y[:, None]))
    fx = (x[None, :] + LENS * gx - x0) / CELL
    fy = (y[:, None] + LENS * gy - y0) / CELL
    dens, _, _ = np.histogram2d(
        fy.ravel(), fx.ravel(), bins=(rows, cols), range=((0, rows), (0, cols))
    )
    return gaussian_filter(dens / CELL**2, 0.6)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # upper right on a landscape screen, upper third on a portrait one; on whole cells
    knot = s.pick(landscape=(0.71875, 7 / 18), portrait=(0.62, 0.3), snap=CELL)
    cols, rows = s.w // CELL, s.h // CELL
    kc, kr = int(knot.x) // CELL, int(knot.y) // CELL
    pad = PAD // CELL
    # The pool is fixed and the screen is a window onto it, so every shape shows the same knot.
    dens = caustics(
        s.noise(5),
        ANCHOR[0] - knot.x - PAD,
        ANCHOR[1] - knot.y - PAD,
        cols + 2 * pad,
        rows + 2 * pad,
    )
    # Move the window so the brightest junction near the anchor (a wide blur favors where
    # filaments meet) lands on the knot.
    win = dens[pad + kr - SEARCH : pad + kr + SEARCH + 1, pad + kc - SEARCH : pad + kc + SEARCH + 1]
    wr, wc = np.unravel_index(np.argmax(gaussian_filter(win, 7)), win.shape)
    r0, c0 = pad + wr - SEARCH, pad + wc - SEARCH
    dens = dens[r0 : r0 + rows, c0 : c0 + cols]

    xs, ys = cells(s.inset(0), CELL)
    # light falls off across the screen: 1 at the upper right, 0 and below to the lower left
    diag = (xs / s.w - ys / s.h + 0.35) / 1.35
    fall = np.clip(diag, 0, 1) ** 1.4
    d = np.hypot(xs - knot.x, ys - knot.y)
    focus = gauss(d, 140)
    tone = np.clip((dens - 2.0) / 5, 0, 1) * fall * (1 + 0.8 * focus)
    tone = np.minimum(tone, 0.34 + 0.66 * focus)  # far filaments stay dimmer than the knot
    tone = np.maximum(tone, gauss(d, 22) * np.clip(dens - 1.5, 0, 1) * 1.2)  # a solid hot core
    grid = dot_diffusion(np.clip(tone, 0, 1), 3)

    # The knot's connected core steps down the accent ladder along its filaments, dithered
    # between steps, then hands over to the UI tones.
    lab, _ = label((grid > 0) & (d < 170), np.ones((3, 3)))
    core = (lab == lab[kr, kc]) & (lab > 0)
    bay = bayer(8)[np.arange(rows)[:, None] % 8, np.arange(cols)[None, :] % 8]
    step = np.clip((135 - d) / 37 + bay - 0.5, 0, 3).astype(np.int64)
    out = np.where(core & (step > 0), step + 2, grid)
    grid_runs(s, out, [None, UI, UI_ALT, ACCENT_6, ACCENT_3, ACCENT], CELL)

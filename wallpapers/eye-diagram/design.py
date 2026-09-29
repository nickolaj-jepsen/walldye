"""An oscilloscope eye diagram: random bit streams folded onto two bit periods and dithered in square cells, with a hexagonal test mask and three hits inside it."""

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.ndimage import distance_transform_edt
from scipy.special import ndtr

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, UI_HI, Canvas, NpRng, P, Rect, Vec, design, mix
from walldye.pixel import dither, glyphs, grid_runs

CELL = 4  # dither cell
UI_PX, SWING = 720, 480  # one bit period across; rail to rail
NX, NY, DIV_H = 10, 8, 100  # graticule divisions (two bit periods wide) and division height
CLEAR = 34  # how far the mask keeps from the trace cloud
TONES = (None, mix(BG, BG_ALT, 0.9), UI, UI_ALT, UI_HI)  # trace density, sparse to dense
HIT = len(TONES)  # grid index of the mask hits, drawn in ACCENT
LABEL = "2.5 Gb/s  UI 400ps  MASK HITS 3"


def persistence(
    rng: NpRng, c: Vec, cols: int, rows: int, n: int = 4000, sigma: float = 0.135
) -> NDArray[np.float64]:
    """Log-scaled hit counts per CELL, shape (rows, cols), normalized to a peak of 1.

    `n` random six-bit streams with jittered edges, band-limited by a Gaussian of `sigma` bit
    periods (10-90% rise about 0.35 of a period), are folded so the bit edges cross at
    `c.x` ± UI_PX / 2, and sampled once per pixel across the two periods centered on `c`.
    """
    t = np.arange(-0.5, 1.5, 1 / UI_PX)
    bits = rng.integers(0, 2, (n, 6)).astype(float)
    edges = np.arange(-3, 2)[None, :] + rng.normal(0, 0.045, (n, 5))
    v = np.repeat(bits[:, :1], t.size, 1)
    for k in range(5):
        # a Gaussian-filtered step is the normal CDF
        v += (bits[:, k + 1] - bits[:, k])[:, None] * ndtr((t - edges[:, k : k + 1]) / sigma)
    xs = c.x - UI_PX / 2 + t * UI_PX
    y = c.y + SWING / 2 - SWING * v + rng.normal(0, 5, (n, 1)) + rng.normal(0, 2, (n, t.size))
    ci = np.clip(xs // CELL, 0, cols - 1).astype(int)
    rj = np.clip(y // CELL, 0, rows - 1).astype(int)
    hist = np.bincount((rj * cols + ci).ravel(), minlength=rows * cols).reshape(rows, cols)
    return np.log1p(hist) / np.log1p(hist.max())


def fit_mask(hist: NDArray[np.float64], c: Vec) -> list[Vec]:
    """Hexagon about `c`, clockwise from its left point, keeping about CLEAR from every cell
    where `hist` reaches 0.05, with its slanted edges as steep as that allows."""
    dist = distance_transform_edt(hist < 0.05) * CELL

    def room(pts: ArrayLike) -> NDArray[np.float64]:
        """Distance to the cloud at each (x, y) row of `pts`."""
        ij = (np.asarray(pts) // CELL).astype(int)
        return dist[ij[:, 1], ij[:, 0]]

    cx, cy = int(c.x), int(c.y)
    ys = np.arange(cy, 0, -1)
    top = int(ys[np.argmax(room(np.column_stack([np.full_like(ys, cx), ys])) < CLEAR)]) + 2
    xs = np.arange(cx, 0, -1)
    left = int(xs[np.argmax(room(np.column_stack([xs, np.full_like(xs, cy)])) < CLEAR)]) + 2
    k = np.arange(41)[:, None]

    def clears(sx: int) -> bool:
        """Whether the edge from the left point to the upper corner at `sx` keeps its distance."""
        edge = np.array([left, cy]) + np.array([sx - left, top - cy]) * k / 40
        return bool(room(edge).min() >= CLEAR - 4)

    sx = next((x for x in range(left + 20, cx) if clears(x)), cx)
    half = [Vec(left, cy), Vec(sx, top), Vec(2 * cx - sx, top)]
    return half + [c * 2 - p for p in half]


@design()
def draw(s: Canvas) -> None:
    c = s.center
    g = Rect(c.x - UI_PX, c.y - NY * DIV_H / 2, 2 * UI_PX, NY * DIV_H)
    lines = P()
    for i in range(NX + 1):
        lines.M(g.x + i * g.w / NX, g.y).V(g.y1)
    for j in range(NY + 1):
        lines.M(g.x, g.y + j * g.h / NY).H(g.x1)
    s.stroke(lines, BG_ALT, 1.2)
    ticks = P()
    for k in range(1, 5 * NX):
        ticks.M(g.x + k * g.w / (5 * NX), c.y - 5).V(c.y + 5)
    for k in range(1, 5 * NY):
        ticks.M(c.x - 5, g.y + k * g.h / (5 * NY)).H(c.x + 5)
    s.stroke(ticks, UI_ALT, 1.2)

    hist = persistence(s.np_rng(11), c, s.w // CELL, s.h // CELL)
    # Rails saturate the histogram; capping lets crossings and rails share one peak tone.
    tone = np.clip((hist - 0.1) / 0.56, 0, 1) ** 1.7 * 0.8
    grid = dither(tone, len(TONES), method="bluenoise", rng=s.np_rng(3))

    mask = fit_mask(hist, c)
    (_, my), (sx, top), (rx, _), (r, _), _, (_, bot) = mask
    for x, y in [(sx + 40, top + 4), (rx - 60, bot - 12), (r - 24, my - 12)]:
        i, j = int(x // CELL), int(y // CELL)
        grid[j : j + 2, i : i + 2] = HIT  # two cells square
    grid_runs(s, grid, (*TONES, ACCENT), CELL)

    s.stroke(P().poly(mask, closed=True), ACCENT, 2)
    glyphs(s, LABEL, UI_ALT, at=(g.x + 16, g.y1 - 24), font="5x8", px=2)

"""A broadcast vectorscope reading color bars: a hexagonal trace with pixel-binned persistence, and one lit cell cluster on the skin-tone line."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_2,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    NpRng,
    P,
    Vec,
    design,
    polar,
)
from walldye.pixel import glyphs, grid_runs

type Pts = NDArray[np.float64]

R = 440  # graticule radius
SCALE = 0.86 * R / 0.632  # the R bar's chroma (|UV| = 0.632, the largest) lands on 86% of R
# The six bars in trace order, with their RGB levels.
BARS = (
    ("R", (1, 0, 0)),
    ("MG", (1, 0, 1)),
    ("B", (0, 0, 1)),
    ("CY", (0, 1, 1)),
    ("G", (0, 1, 0)),
    ("YL", (1, 1, 0)),
)
SKIN = -123  # the skin-tone (I) line, screen degrees


def chroma(rgb: tuple[int, int, int]) -> tuple[float, float]:
    """Graticule radius (px) and screen angle (degrees, y down) of a 100% bar's (U, V) point."""
    r, g, b = rgb
    y = 0.299 * r + 0.587 * g + 0.114 * b
    u, v = 0.492 * (b - y), 0.877 * (r - y)
    return SCALE * math.hypot(u, v), -math.degrees(math.atan2(v, u))


TARGETS = tuple((name, *chroma(rgb)) for name, rgb in BARS)  # (label, radius, deg)


def trace_glow(hexa: Pts, rng: NpRng, n: int = 7000, sd: float = 1.6) -> Pts:
    """Phosphor persistence: `n` points spread along the closed trace's edges in turn, each
    offset across its edge by a normal spread of `sd` px."""
    k = np.arange(n) % len(hexa)
    a = hexa[k]
    d = hexa[(k + 1) % len(hexa)] - a
    t, off = rng.random(n), rng.normal(0, sd, n)
    across = np.stack([-d[:, 1], d[:, 0]], axis=1) / np.hypot(d[:, 0], d[:, 1])[:, None]
    return a + t[:, None] * d + off[:, None] * across


def binned(pts: Pts, origin: Vec, cell: int) -> NDArray[np.int64]:
    """Point counts per `cell`-px square of a grid covering the graticule's bounding square,
    (0, 0) at `origin`; points outside it are dropped."""
    n = math.ceil(2 * R / cell)
    ij = np.floor((pts - np.asarray(origin)) / cell).astype(np.int64)
    ok = ((ij >= 0) & (ij < n)).all(axis=1)
    grid = np.zeros((n, n), dtype=np.int64)
    np.add.at(grid, (ij[ok, 1], ij[ok, 0]), 1)
    return grid


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of center on a landscape screen, leaving the left for windows; low on a portrait
    # one, under the clock; on even units so the 2 px cells and the square marks stay crisp
    c = s.pick(landscape=(31 / 48, 0.5), portrait=(0.5, 0.6), snap=2)
    grid_at = c - (R, R)

    rings = P()
    for k in range(1, 5):
        rings.circle(c, R * k / 5)
    s.stroke(rings, BG_ALT, 1.2)
    s.stroke(P().circle(c, R), UI, 1.6)

    # U and V axes, with a tick every 4% of the radius and a longer one every 20%
    ax = P().M(c.x - R, c.y).H(c.x + R).M(c.x, c.y - R).V(c.y + R)
    for k in range(-25, 26):
        if k:
            t = 6 if k % 5 == 0 else 3.5
            ax.M(c.x + k * R / 25, c.y - t).V(c.y + t).M(c.x - t, c.y + k * R / 25).H(c.x + t)
    s.stroke(ax, UI_ALT, 1.2)

    ticks = P()
    for deg in range(0, 360, 2):
        ticks.M(polar(c, R, deg=deg)).L(polar(c, R + (12 if deg % 10 == 0 else 6), deg=deg))
    s.stroke(ticks, BG_ALT, 1.2)

    # Targets: the 75% box (±7.5% of full chroma, ±5°) and the 100% box (±5%, ±2.5°).
    boxes = P()
    for _, mag, deg in TARGETS:
        boxes.arc_band(c, 0.675 * mag, 0.825 * mag, deg=(deg - 5, deg + 5))
        boxes.arc_band(c, 0.95 * mag, 1.05 * mag, deg=(deg - 2.5, deg + 2.5))
    s.stroke(boxes, UI_ALT, 1.3)
    for name, mag, deg in TARGETS:
        x, y = polar(c, mag + 34, deg=deg)
        glyphs(
            s, name, UI_ALT, at=(round(x), round(y) - 8), font="5x8", px=2, gap=1, anchor="middle"
        )

    # 75% bars: the trace, a persistence band binned to 2 px cells (UI where it piles up)
    hexa = [polar(c, 0.75 * mag, deg=deg) for _, mag, deg in TARGETS]
    rng = s.np_rng(4)
    glow = binned(trace_glow(np.array(hexa), rng), grid_at, 2)
    grid_runs(s, np.where(glow > 5, 2, np.minimum(glow, 1)), [None, BG_ALT, UI], 2, grid_at)
    s.stroke(P().poly(hexa, closed=True), UI_HI, 1.4, join="round")
    dots = P().rect(c.x - 3, c.y - 3, 6, 6)
    for p in hexa:
        dots.rect(round(p.x) - 3, round(p.y) - 3, 6, 6)
    s.fill(dots, UI_HI)

    # The I line: full accent through the skin cluster, a darker step out to the 80% ring.
    mid = polar(c, 0.46 * R, deg=SKIN)
    s.stroke(P().M(c).L(mid), ACCENT, 1.5)
    s.stroke(P().M(mid).L(polar(c, 0.8 * R, deg=SKIN)), ACCENT_2, 1.3)
    along, across = rng.normal(0.32, 0.06, 420) * R, rng.normal(0, 0.015, 420) * R
    u = polar((0, 0), 1, deg=SKIN)
    skin = binned(c + np.outer(along, u) + np.outer(across, u.perp()), grid_at, 3)
    # single hits in the darker step, cells hit twice or more in full accent
    grid_runs(s, np.minimum(skin, 2), [None, ACCENT_2, ACCENT], 3, grid_at)

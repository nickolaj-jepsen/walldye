"""A halved nautilus shell as a weighted-Voronoi stipple plate, its innermost chambers picked out."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

from walldye import ACCENT, ACCENT_2, UI_ALT, UI_HI, Canvas, P, Rect, Vec, design
from walldye.field import cells, gauss
from walldye.pixel import glyphs

type Field = NDArray[np.float64]

B = math.log(2.4) / (2 * math.pi)  # whorl radius grows ~2.4x per turn
RMAX = 400
TURNS = 4
SEPTA = 2 * math.pi / 10  # chamber spacing
LIVING = 2.3  # radians of body chamber without septa
TMAX = 2 * math.pi * TURNS
T0 = 0.3 * math.pi  # the protoconch: whorl angle where the shell begins
ROT = math.radians(140) - TMAX  # aperture faces lower-left
A0 = RMAX / math.exp(B * TMAX)  # spiral radius at whorl angle 0
N, ITERS, CELL = 8000, 40, 2  # dots, Lloyd iterations, tone-field cell
HALF = int(RMAX * 1.3 / CELL) * CELL  # half-width of the square tone field
ACCENT_T = (T0 + 9 * SEPTA, T0 + 16 * SEPTA)  # septum-space angles bounding the accent chambers
# Dot paints by index: body, walls and septa, outer accent chambers, innermost chambers.
PAINTS = (UI_ALT, UI_HI, ACCENT_2, ACCENT)
RADII = (1.3, 1.6, 1.8)  # dot radius for local tone below 0.3, below 0.6, and above


def shell(xs: Field, ys: Field) -> tuple[Field, Field]:
    """Tone in [0, 1] and the septum-space whorl angle (-1 outside the shell) at coil-relative
    points."""
    rho = np.hypot(xs, ys) + 1e-6
    phi = np.mod(np.arctan2(ys, xs) - ROT, 2 * np.pi)
    # Smallest whorl angle t = phi + 2πk whose outer wall still lies outside rho.
    k = np.ceil((np.log(rho / A0) / B - phi) / (2 * np.pi))
    t = phi + 2 * np.pi * k
    outer, inner = A0 * np.exp(B * t), A0 * np.exp(B * (t - 2 * np.pi))
    h = outer - inner
    u = np.clip((rho - inner) / h, 0, 1)  # 0 at the inner wall, 1 at the outer wall
    # The aperture lip bows outward, rounded at both ends.
    tend = TMAX + 0.14 * np.sin(np.pi * u) ** 0.7
    inside = (t <= tend) & (t >= T0)
    # Line widths grow with the whorl height h, so gauss gets distances already divided by them.
    edge = np.minimum(np.minimum(rho - inner, outer - rho), (t - T0) * rho)
    wall = gauss(edge / (0.014 * h + 0.9), 1)

    # Septa bow back toward the coil, deepest mid-whorl.
    ts = t + 0.9 * SEPTA * np.sin(np.pi * u) ** 1.2
    ph = ts / SEPTA
    near = np.abs(ph - np.round(ph)) * SEPTA * rho
    septum = np.where(ts < TMAX - LIVING, gauss(near / (0.012 * h + 0.8), 1), 0)

    # The accent chambers stipple as an even field; the rest thins toward the outer wall.
    body = np.where(ts < ACCENT_T[1], 0.2, 0.04 + 0.12 * (1 - u) ** 2)
    lip = gauss((tend - t) * rho / (0.016 * h + 0.9), 1)  # thickened aperture rim
    tone = np.maximum.reduce([body, wall, 0.8 * lip, 0.85 * septum])
    return np.where(inside, tone, 0), np.where(inside, ts, -1)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of center on a landscape screen, the upper middle on a portrait one
    c = s.pick(landscape=(1240 / 1920, 520 / 1080), portrait=(0.5, 0.44))
    xs, ys = cells(Rect(-HALF, -HALF, 2 * HALF, 2 * HALF), CELL)
    tone, ts = shell(xs, ys)
    tone = gaussian_filter(tone, 0.8)
    tone[ts < 0] = 0
    # Center the shell's bounding box, not its coil, on the focal point.
    rows, cols = np.nonzero(tone > 0.02)
    left, right = xs[0, cols.min()], xs[0, cols.max()]
    top, bottom = ys[rows.min(), 0], ys[rows.max(), 0]
    off = c - Vec((left + right) / 2, (top + bottom) / 2)

    # Weighted Voronoi stippling: seed dots by tone, then move each to its cell's centroid.
    rng = s.np_rng(3)
    w = tone.ravel() ** 1.25
    px = np.stack([xs.ravel(), ys.ravel()], 1)
    pts = px[rng.choice(len(px), N, replace=False, p=w / w.sum())] + rng.uniform(-1, 1, (N, 2))
    keep = w > 0
    pw, pp = w[keep], px[keep]
    for _ in range(ITERS):
        idx = cKDTree(pts).query(pp)[1]
        m = np.bincount(idx, pw, N)
        ok = m > 0
        cx, cy = np.bincount(idx, pw * pp[:, 0], N), np.bincount(idx, pw * pp[:, 1], N)
        pts[ok] = np.stack([cx, cy], 1)[ok] / m[ok, None]

    _, ch = shell(pts[:, 0], pts[:, 1])
    ij = ((pts + HALF) / CELL).astype(int).clip(0, tone.shape[0] - 1)
    v = tone[ij[:, 1], ij[:, 0]]
    heart = (ch >= 0) & (ch < ACCENT_T[0])
    ring = (ch >= 0) & (ch < ACCENT_T[1])
    paint = np.select([heart, ring], [3, 2], (v > 0.35).astype(int))
    size = np.digitize(v, (0.3, 0.6))
    at = pts + off
    # Dots are zero-length round-capped strokes: a few bytes each instead of two arcs.
    for k, r in enumerate(RADII):
        with s.buckets(PAINTS, "stroke", stroke_width=2 * r, stroke_linecap="round") as dots:
            for (x, y), i in zip(at[size == k], paint[size == k], strict=True):
                dots[i].M(x, y).H(x)

    # Plate furniture: a figure number above the shell and a 5 cm scale bar below it.
    x0, y0, y1 = round(left + off.x), round(top + off.y), round(bottom + off.y)
    bar = P().M(x0, y1 + 40).H(x0 + 120)
    bar.M(x0, y1 + 36).V(y1 + 44).M(x0 + 120, y1 + 36).V(y1 + 44)
    s.stroke(bar, UI_ALT, 1.5)
    glyphs(s, "5 cm", UI_ALT, at=(x0 + 40, y1 + 52), font="5x8", px=2)
    glyphs(s, "Fig. 3", UI_ALT, at=(x0, y0 - 16), font="5x8", px=2)

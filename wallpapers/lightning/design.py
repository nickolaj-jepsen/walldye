"""A lightning strike built by midpoint displacement, with tapering branches under a dithered cloud base."""

import math

import numpy as np
from numpy.typing import NDArray
from shapely import Polygon, unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_8,
    ACCENT_HI,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    NpRng,
    P,
    by_regime,
    design,
    mix,
)
from walldye.field import cells, gauss
from walldye.geom import ribbon
from walldye.pixel import dither, grid_runs

type Pts = NDArray[np.float64]

BOLT = 12  # random stream for the channel and its branches
CELL = 3  # dither cell of the cloud and the lit ground
ROUGH = 0.13  # spread of each midpoint's sideways kick, as a fraction of its segment
STEP = 12.0  # finest segment length
GROUND = by_regime(BG_DEEP, BG_ALT)
SKY = (None, BG_ALT, UI, UI_ALT, BG)  # cloud dither rungs, then the veil over the channel
# Lit ground rungs: as SKY in the dark regime; in the light one, paler than GROUND.
LIT = (None, by_regime(BG_ALT, mix(BG, BG_ALT, 0.5)), by_regime(UI, BG), by_regime(UI_ALT, BG))
# Branch tones from root to tip, per order (1, 2), and the root width of each order.
FADE = ((ACCENT_1, ACCENT_3, ACCENT_5), (ACCENT_3, ACCENT_5))
WIDTH = (2.8, 1.8)
# The return stroke's layered strokes, outermost first: (paint, width).
HALO = ((ACCENT_8, 30.0), (ACCENT_6, 16.0), (ACCENT_3, 8.0), (ACCENT, 4.4), (ACCENT_HI, 1.5))


def displace(a: Pts, b: Pts, rng: NpRng) -> Pts:
    """A jagged polyline from `a` to `b`: every segment is split at its midpoint, pushed sideways
    by a Laplace draw of ROUGH times its length (capped at three times that), until no segment
    is longer than STEP. The kick scales with the segment, so the kinks look alike at every
    scale."""
    pts = np.array([a, b], np.float64)
    while True:
        seg = np.diff(pts, axis=0)
        if np.hypot(seg[:, 0], seg[:, 1]).max() <= STEP:
            return pts
        kick = np.clip(rng.laplace(0, ROUGH, len(seg)), -3 * ROUGH, 3 * ROUGH)
        mid = (pts[:-1] + pts[1:]) / 2 + np.stack([-seg[:, 1], seg[:, 0]], 1) * kick[:, None]
        out = np.empty((2 * len(pts) - 1, 2))
        out[0::2], out[1::2] = pts, mid
        pts = out


def along(pts: Pts) -> NDArray[np.float64]:
    """Arc length at each vertex, as a fraction of the whole."""
    d = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    return d / d[-1]


def forks(
    rng: NpRng,
    pts: Pts,
    order: int,
    length: float,
    floor: float,
    wall: float,
    out: list[tuple[int, Pts]],
) -> None:
    """Grow branches off the strand `pts` into `out` as (order, points), recursing to order 2.
    Each leaves 20-50 degrees off the strand's local heading, mostly on alternate sides, kept
    within 55 degrees of straight down, and is shorter the lower it starts; its end is pulled
    in to stay above y = `floor` and between x = 60 and x = `wall`."""
    t = along(pts)
    count = (5, 2)[order - 1]
    lo, hi = ((0.1, 0.62), (0.1, 0.7))[order - 1]
    side = rng.choice((-1.0, 1.0))
    for u in np.sort(rng.uniform(lo, hi, rng.integers(count - 1, count + 1))):
        i = int(np.searchsorted(t, u))
        d = pts[min(i + 4, len(pts) - 1)] - pts[max(i - 4, 0)]
        side = -side if rng.random() < 0.7 else side
        head = math.atan2(d[1], d[0]) + side * math.radians(rng.uniform(20, 50))
        head = min(max(head, math.radians(35)), math.radians(145))
        span = length * rng.uniform(0.3, 0.6) * (1 - 0.65 * u)
        end = pts[i] + span * np.array([math.cos(head), math.sin(head)])
        if end[1] > floor:
            end = pts[i] + (end - pts[i]) * (floor - pts[i][1]) / (end[1] - pts[i][1])
        edge = wall if end[0] > wall else max(end[0], 60)
        if edge != end[0]:
            end = pts[i] + (end - pts[i]) * (edge - pts[i][0]) / (end[0] - pts[i][0])
        if np.hypot(*(end - pts[i])) < 24:
            continue
        branch = displace(pts[i], end, rng)
        out.append((order, branch))
        if order < 2:
            forks(rng, branch, order + 1, span, floor, wall, out)


@design(aspects="any")
def draw(s: Canvas) -> None:
    rng = s.np_rng(BOLT)
    noise = s.noise(5)
    if s.landscape:
        top, ground = 200.0, s.h - 150.0
        xr = 0.635 * s.w
        xg = xr - 90
    else:
        top, ground = 0.15 * s.h, 0.86 * s.h
        xr, xg = 0.6 * s.w, 0.5 * s.w

    def base(x: NDArray[np.float64]) -> NDArray[np.float64]:
        """The cloud base's height at x: ragged, and a little lower over the strike."""
        return top + 120 * noise.fbm(x / 340, 0.5, octaves=4) + 30 * gauss(x - xr, 500)

    root = np.array([xr, float(base(np.array([xr]))[0]) - 50])
    hill = ground - 10 * np.clip(noise.fbm(xg / 400, 3.5), 0, 1)
    main = displace(root, np.array([xg, hill]), rng)
    branches: list[tuple[int, Pts]] = []
    forks(rng, main, 1, ground - root[1], ground - 40, s.w - 60, branches)
    tones: dict[tuple[int, int], list[Polygon]] = {}
    for order, pts in branches:
        k = order - 1
        t = along(pts)
        w = np.maximum(0.45, WIDTH[k] * (1 - t) ** 0.8)
        n = len(FADE[k])
        for j in range(n):
            sel = (t >= j / n - 1e-9) & (t <= (j + 1) / n + 0.02)
            if sel.sum() > 1:
                tones.setdefault((k, j), []).append(Polygon(ribbon(pts[sel], w[sel])).buffer(0))

    # the bolt is cut a little inside the cloud base, and the cloud's edge drawn over the cut
    tx = np.linspace(0, s.w, int(s.w // 8) + 1)
    with s.clip() as below:
        below.add(P().poly([(0, s.h), *zip(tx, base(tx) - 25), (s.w, s.h)], closed=True))
    with s.group(clip_path=below.ref, stroke_linecap="round", stroke_linejoin="round"):
        # the return stroke's halo, then the branches, then its core
        for paint, w in HALO[:3]:
            s.stroke(P().poly(main), paint, w)
        for k, j in sorted(tones, key=lambda kj: (-kj[0], -kj[1])):
            s.fill(P().shape(unary_union(tones[k, j])), FADE[k][j])
        for paint, w in HALO[3:]:
            s.stroke(P().poly(main), paint, w)

    # ground over the foot of the halo, lit round the strike
    horizon = np.stack([tx, ground - 10 * np.clip(noise.fbm(tx / 400, 3.5), 0, 1)], 1)
    land = P().poly([(0, s.h), *horizon.tolist(), (s.w, s.h)], closed=True)
    s.fill(land, GROUND)
    with s.clip() as clip:
        clip.add(land)
    xs, ys = cells(s.inset(0), CELL)
    band = ys[:, 0] > ground - 20
    gx, gy = xs[band], ys[band]
    lamp = np.clip(0.72 * gauss(np.hypot(gx - xg, (gy - hill) * 3), 320) - 0.08, 0, 1)
    with s.group(clip_path=clip.ref):
        grid = dither(lamp, 4, method="bluenoise", rng=s.np_rng(8))
        grid_runs(s, grid, LIT, CELL, (0, float(gy[0, 0]) - CELL / 2))

    # cloud: dithered density under a ragged base, lit round the channel's root
    rows = int((top + 200) // CELL)
    cx, cy = xs[:rows], ys[:rows]
    depth = np.clip((base(cx[0])[None, :] - cy) / 70, 0, 1)
    body = depth * (0.5 + 0.5 * gauss(cx - xr, 900))
    body *= 0.5 + 0.3 * noise.fbm(cx / 180, cy / 90 + 7, octaves=3)
    lit = gauss(np.hypot(cx - xr, (cy - root[1] - 60) * 2.4), 320) * depth**0.5
    grid = dither(np.clip(0.75 * body + 0.6 * lit, 0, 1), 4, method="bluenoise", rng=s.np_rng(7))
    # empty cells over the channel are veiled as often as the cloud is deep, so it fades into
    # the cloud instead of showing through every gap
    veil = dither(depth, 2, method="bluenoise", rng=s.np_rng(9)) == 1
    grid[(grid == 0) & veil & (np.abs(cx - xr) < 160)] = 4
    grid_runs(s, grid, SKY, CELL)

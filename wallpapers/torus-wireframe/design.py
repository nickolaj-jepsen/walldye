"""A wireframe torus rising from the bottom-left corner, its hidden lines found by ray marching."""

import math
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from skimage.measure import approximate_polygon

from walldye import ACCENT, UI, UI_ALT, Canvas, P, Path, Vec, design
from walldye.field import runs

type Arr = NDArray[np.float64]
type Curve = Callable[[Arr], tuple[Arr, Arr]]  # t -> (points to draw, points to test)

R, r = 580, 235  # ring and tube radii at full size
TILT, SPIN = math.radians(58), math.radians(-8)
MERIDIANS, PARALLELS, ACCENT_U = 30, 18, 1  # accent meridian: fully in frame, right of the hole
LEFT, DROP = 440, 155  # center: this far right of the left edge and above the bottom edge
REACH = 811  # projected half-width at full size: the far rim ends at LEFT + REACH
MARGIN = 100  # the least room between the far rim and the right edge
TOL = 0.1  # Douglas-Peucker tolerance for the drawn lines, in canvas units

# local torus frame -> view space (screen x, screen y, depth towards the viewer)
M = np.array(
    [[math.cos(SPIN), -math.sin(SPIN), 0], [math.sin(SPIN), math.cos(SPIN), 0], [0, 0, 1]]
) @ np.array([[1, 0, 0], [0, math.cos(TILT), -math.sin(TILT)], [0, math.sin(TILT), math.cos(TILT)]])


def surface(u: Arr, v: Arr) -> tuple[Arr, Arr]:
    """View-space points and unit normals for same-shape arrays u (azimuth), v (tube angle)."""
    n = np.stack([np.cos(v) * np.cos(u), np.cos(v) * np.sin(u), np.sin(v)], -1)
    center = np.stack([R * np.cos(u), R * np.sin(u), 0 * u], -1)
    return (center + r * n) @ M.T, n @ M.T


def visible(p: Arr) -> NDArray[np.bool_]:
    """True for each view-space point whose ray towards the viewer (+z) never enters the torus."""
    t = np.arange(1.5, 2 * (R + r), 2.0)
    out = []
    for c in range(0, len(p), 500):
        q = p[c : c + 500, None, :] + t[None, :, None] * np.array([0, 0, 1.0])
        loc = q @ M  # inverse of an orthonormal rotation
        f = (np.hypot(loc[..., 0], loc[..., 1]) - R) ** 2 + loc[..., 2] ** 2 - r * r
        out.append(~(f < 0).any(1))
    return np.concatenate(out)


def meridian(u: float) -> Curve:
    """The tube circle at azimuth u, tested on the surface itself."""

    def fn(t: Arr) -> tuple[Arr, Arr]:
        p, _ = surface(np.full_like(t, u), t)
        return p, p

    return fn


def parallel(v: float) -> Curve:
    """The ring at tube angle v, tested on the surface itself."""

    def fn(t: Arr) -> tuple[Arr, Arr]:
        p, _ = surface(t, np.full_like(t, v))
        return p, p

    return fn


def outline(off: float) -> Curve:
    """One branch of the silhouette, where the normal is square to the view axis; off is 0 or pi."""
    n = M[2]  # view z in local coords

    def fn(t: Arr) -> tuple[Arr, Arr]:
        p, normal = surface(t, np.arctan2(-(n[0] * np.cos(t) + n[1] * np.sin(t)), n[2]) + off)
        return p, p + 1.5 * normal  # nudged off the surface: the ray grazes it here

    return fn


def trace(d: Path, fn: Curve, t: Arr, c: Vec, k: float) -> None:
    """Append to `d` the visible stretches of `fn` over `t`, each bisected out to its exact
    visibility edge, scaled by `k` about the torus center `c`."""
    pts, test = fn(t)
    vis = visible(test)
    flip = np.flatnonzero(vis[1:] != vis[:-1])
    lo, hi = t[flip], t[flip + 1]  # vis(lo) == vis[flip] on every iteration
    for _ in range(14 if len(flip) else 0):
        mid = (lo + hi) / 2
        same = visible(fn(mid)[1]) == vis[flip]
        lo, hi = np.where(same, mid, lo), np.where(same, hi, mid)
    edge = dict(zip(flip.tolist(), fn((lo + hi) / 2)[0], strict=True))
    for i, j in runs(vis):
        ends = ([edge[i - 1]] if i > 0 else [], [edge[j - 1]] if j < len(t) else [])
        run = np.array([*ends[0], *pts[i:j], *ends[1]])
        if len(run) > 1:
            d.poly(approximate_polygon(c + k * run[:, :2], TOL))


@design(aspects="any")
def draw(s: Canvas) -> None:
    k = min(1.0, (s.w - MARGIN) / (LEFT + REACH))  # a narrow screen shrinks the torus to fit
    c = Vec(LEFT * k, s.h - DROP * k)
    grid, sil, acc = P(), P(), P()
    v = np.linspace(0, 2 * math.pi, 721)
    u = np.linspace(0, 2 * math.pi, 1441)
    for m in range(MERIDIANS):
        trace(acc if m == ACCENT_U else grid, meridian(2 * math.pi * m / MERIDIANS), v, c, k)
    for j in range(PARALLELS):
        trace(grid, parallel(2 * math.pi * j / PARALLELS), u, c, k)
    for off in (0, math.pi):
        trace(sil, outline(off), u, c, k)
    s.stroke(grid, UI, 1.2)
    s.stroke(sil, UI_ALT, 1.6, cap="round")
    s.stroke(acc, ACCENT, 3, cap="round")

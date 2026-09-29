"""A crescent moon drawn as one unbroken line: a traveling-salesman tour through stipples weighted by sunlight."""

import math
from collections import deque

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from walldye import ACCENT, UI, Canvas, NpRng, P, Params, design, knob, polar

type Points = NDArray[np.float64]
type Order = NDArray[np.intp]

R = 320  # moon radius
SUN = polar((0, 0), 1, deg=142)  # where the sun lies across the disc: lower left
STIPPLES = 41_900  # stipples per unit of mean brightness over the moon's square


class Moon(Params):
    phase: float = knob(
        default=113,
        lo=30,
        hi=150,
        unit="deg",
        doc="angle between the sun and the viewer, seen from the moon; 0 is full, 180 new",
    )


def brightness(x: Points, y: Points, light: Points) -> Points:
    """Stipple density at unit-disc coordinates (x, y) under a unit `light` vector (z toward the
    viewer): Lambert shading with a floor, and zero off the lit part."""
    rr = x * x + y * y
    z = np.sqrt(np.clip(1 - rr, 0, None))
    lit = x * light[0] + y * light[1] + z * light[2]
    # the floor keeps terminator cells small; the cutoff gives the inner curve a clean edge
    return np.where((rr < 1) & (lit > 0.04), 0.15 + 0.85 * np.clip(lit, 0, None) ** 1.3, 0)


def stipple(rng: NpRng, light: Points, iters: int = 12, res: int = 700) -> Points:
    """Weighted Voronoi stippling (Secord 2002) of the brightness field, in unit coordinates; the
    stipple count follows the field's total brightness, so the spacing is the same at every phase.
    """
    g = np.linspace(-1, 1, res)
    gx, gy = np.meshgrid(g, g)
    wgt = brightness(gx, gy, light).ravel()
    n = round(STIPPLES * wgt.mean())
    keep = wgt > 1e-3
    px, pw = np.c_[gx.ravel(), gy.ravel()][keep], wgt[keep]
    pts = px[rng.choice(len(px), n, replace=False, p=pw / pw.sum())]
    for _ in range(iters):
        _, owner = cKDTree(pts).query(px)
        m = np.bincount(owner, pw, n)
        ok = m > 0
        pts[ok, 0] = np.bincount(owner, pw * px[:, 0], n)[ok] / m[ok]
        pts[ok, 1] = np.bincount(owner, pw * px[:, 1], n)[ok] / m[ok]
    return pts


def nearest_neighbor(pts: Points, tree: cKDTree) -> Order:
    """Visit order that always steps to the closest unvisited point, starting at point 0."""
    n = len(pts)
    seen = np.zeros(n, bool)
    order = [0]
    seen[0] = True
    for _ in range(n - 1):
        cand: list[int] = []
        for kk in (16, 64, 256, n):
            _, near = tree.query(pts[order[-1]], min(kk, n))
            cand = [c for c in np.atleast_1d(near).tolist() if not seen[c]]
            if cand:
                break
        order.append(cand[0])
        seen[cand[0]] = True
    return np.array(order, np.intp)


def tour(pts: Points, k: int = 10) -> Order:
    """A closed tour visiting every point once: nearest-neighbor order, then 2-opt and Or-opt
    moves over each point's `k` nearest neighbors until no move shortens it."""
    n = len(pts)
    tree = cKDTree(pts)
    nbrs: list[list[int]] = tree.query(pts, k + 1)[1][:, 1:].tolist()
    xs: list[float] = pts[:, 0].tolist()
    ys: list[float] = pts[:, 1].tolist()
    t = nearest_neighbor(pts, tree)
    pos = np.empty(n, np.intp)
    pos[t] = np.arange(n)

    def d(a: int, b: int) -> float:
        return math.hypot(xs[a] - xs[b], ys[a] - ys[b])

    def place(lo: int, block: Order) -> None:
        t[lo : lo + len(block)] = block
        pos[block] = np.arange(lo, lo + len(block))

    def two_opt(a: int) -> list[int]:
        """Swap edges (a, b) and (c, e) for (a, c) and (b, e), b and e both after or both before."""
        for step in (1, -1):
            ia = int(pos[a])
            b = int(t[(ia + step) % n])
            dab = d(a, b)
            for c in nbrs[a]:
                dac = d(a, c)
                if dac >= dab:
                    break
                ic = int(pos[c])
                e = int(t[(ic + step) % n])
                if c != b and e != a and dac + d(b, e) < dab + d(c, e) - 1e-12:
                    lo, hi = (ia + 1, ic) if step == 1 else (ic, ia - 1)
                    if lo > hi:  # the stretch wraps past the array end: reverse the rest instead
                        lo, hi = hi + 1, lo - 1
                    place(lo, t[lo : hi + 1][::-1].copy())
                    return [a, b, c, e]
        return []

    def or_opt(a: int) -> list[int]:
        """Move the run of one to three points starting at a between two points near its ends."""
        i = int(pos[a])
        for size in (1, 2, 3):
            if i + size > n:
                break
            s1, s2 = a, int(t[i + size - 1])
            p, nx = int(t[i - 1]), int(t[(i + size) % n])
            cut = d(p, s1) + d(s2, nx) - d(p, nx)
            best, at, flip = 1e-12, -1, False
            for end in (s1, s2):
                for c in nbrs[end]:
                    if d(end, c) >= cut:  # the new edge alone costs more than the cut saves
                        break
                    for j in (int(pos[c]), (int(pos[c]) - 1) % n):
                        if (j - i + 1) % n <= size:  # (p, s1), inside the run, or (s2, nx)
                            continue
                        c1, c2 = int(t[j]), int(t[(j + 1) % n])
                        gain = cut + d(c1, c2) - d(c1, s1) - d(s2, c2)
                        gain_flipped = cut + d(c1, c2) - d(c1, s2) - d(s1, c2)
                        if max(gain, gain_flipped) > best:
                            best, at, flip = max(gain, gain_flipped), j, gain_flipped > gain
            if at >= 0:
                c1, c2 = int(t[at]), int(t[(at + 1) % n])
                run = t[i : i + size][::-1].copy() if flip else t[i : i + size].copy()
                if at > i:
                    place(i, np.concatenate([t[i + size : at + 1], run]))
                else:
                    place(at + 1, np.concatenate([run, t[at + 1 : i]]))
                return [p, nx, s1, s2, c1, c2]
        return []

    # don't-look bits: after the first sweep, only points next to a changed edge are retried
    queue = deque(t.tolist())
    queued = [True] * n
    while queue:
        a = queue.popleft()
        queued[a] = False
        for v in two_opt(a) or or_opt(a):
            if not queued[v]:
                queued[v] = True
                queue.append(v)
    return t


@design(aspects="any", variants={"gibbous": Moon(phase=50)})
def draw(s: Canvas[Moon]) -> None:
    c = s.pick(landscape=(0.7135, 0.435), portrait=(0.56, 0.36))
    a = math.radians(s.params.phase)
    light = np.array([SUN.x * math.sin(a), SUN.y * math.sin(a), math.cos(a)])
    pts = stipple(s.np_rng(3), light)
    xy = pts[tour(pts)] * R + c
    # horn tips otherwise end in long straight spikes: drop points with an over-long edge, once
    e = np.hypot(*(np.roll(xy, -1, 0) - xy).T)
    xy = xy[np.maximum(e, np.roll(e, 1)) <= 3 * np.median(e)]
    s.stroke(P().circle(c, R), UI, 1)
    s.stroke(P().poly(xy, closed=True), ACCENT, 1.2, join="round")

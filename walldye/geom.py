"""Geometry helpers: transforms, polylines, curve sampling, ribbons, hatching and scattering.

Point sets are (N, 2) float64 arrays; draw them with P().poly(...) or P().dots(...).
"""

import math
import random
from collections.abc import Callable
from typing import Final, final, overload

import numpy as np
from numpy.typing import ArrayLike, NDArray
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry

from ._affine import Affine
from ._path import _points, ngon_vertices
from ._vec import Num, Point, Rect, Vec, angle, num

__all__ = [
    "Affine",
    "Polyline",
    "bezier_points",
    "hatch",
    "ngon",
    "parts",
    "poisson_disk",
    "ribbon",
    "scatter",
    "spline_points",
]

type _F = NDArray[np.float64]
type _Reals = NDArray[np.integer | np.floating]


def _count(n: object, what: str, least: int) -> int:
    """`n` as an int of at least `least`. Raises TypeError for a non-int (or bool) and
    ValueError below `least`."""
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)):
        raise TypeError(f"{what} takes an int, got {n!r}")
    v = int(n)
    if v < least:
        raise ValueError(f"{what} takes an int >= {least}, got {n!r}")
    return v


def _normals(p: _F, closed: bool) -> _F:
    """Per-vertex unit offset directions of the polyline `p` (no consecutive repeats).

    Each vertex gets the unit bisector of its two segments' normals, an end vertex of an open
    line its one segment's normal; the normal of direction (tx, ty) is (-ty, tx). At a full
    reversal, where the bisector vanishes, the vertex gets its incoming direction.
    """
    loop = np.vstack([p, p[:1]]) if closed else p
    d = np.diff(loop, axis=0)
    size: _F = np.hypot(d[:, 0], d[:, 1])
    t = d / size[:, None]
    seg = np.stack([-t[:, 1], t[:, 0]], axis=1)
    if closed:
        into, out = np.roll(seg, 1, axis=0), seg
        into_t = np.roll(t, 1, axis=0)
    else:
        into = np.vstack([seg[:1], seg])
        out = np.vstack([seg, seg[-1:]])
        into_t = np.vstack([t[:1], t])
    b = into + out
    blen: _F = np.hypot(b[:, 0], b[:, 1])
    flat = blen < 1e-12
    b[flat] = into_t[flat]
    blen[flat] = 1.0
    return b / blen[:, None]


@final
class Polyline:
    """A polyline measured by arc length, open or closed.

    `pts` is (N, 2) float64 and read-only, with consecutive repeated points removed (on a
    closed line also a last point equal to the first, since closing is implicit).
    """

    def __init__(self, pts: ArrayLike, *, closed: bool = False) -> None:
        """Raises ValueError for another shape than (N, 2), a non-finite coordinate, or fewer
        than 2 points after removing repeats; TypeError for non-numeric points or a non-bool
        `closed`."""
        if not isinstance(closed, bool):
            raise TypeError(f"Polyline closed takes a bool, got {closed!r}")
        p = _points(pts, "Polyline")
        if len(p) > 1:
            keep = np.ones(len(p), dtype=bool)
            keep[1:] = np.any(p[1:] != p[:-1], axis=1)
            p = p[keep]
        if closed and len(p) > 1 and np.array_equal(p[:1], p[-1:]):
            p = p[:-1]
        if len(p) < 2:
            raise ValueError(f"a Polyline needs at least 2 distinct points, got {len(p)}")
        p.setflags(write=False)
        self.pts: Final = p
        self.closed: Final = closed
        self._loop: Final[_F] = np.vstack([p, p[:1]]) if closed else p
        d = np.diff(self._loop, axis=0)
        seg: _F = np.hypot(d[:, 0], d[:, 1])
        self._seg: Final[_F] = seg
        self._cum: Final[_F] = np.concatenate([[0.0], np.cumsum(seg)])

    def __repr__(self) -> str:
        return f"Polyline({len(self.pts)} points, closed={self.closed}, length={self.length:g})"

    @property
    def length(self) -> float:
        """The total arc length, including the closing segment of a closed line."""
        return float(self._cum[-1])

    def _wrap(self, d: _F) -> _F:
        if not self.closed:
            return d
        out: _F = np.mod(d, self.length)
        return out

    def _wrap1(self, d: float) -> float:
        return d % self.length if self.closed else d

    @overload
    def at(self, d: Num) -> Vec: ...
    @overload
    def at(self, d: _Reals) -> _F: ...
    def at(self, d: Num | _Reals) -> Vec | _F:
        """The point at arc length `d` from the start, clamped to [0, length] on an open line
        and wrapping on a closed one. An array of distances gives an array of shape
        d.shape + (2,).

        Raises TypeError for a non-number and ValueError for NaN or infinity.
        """
        if isinstance(d, np.ndarray):
            u = np.asarray(d, dtype=np.float64)
            if not bool(np.isfinite(u).all()):
                raise ValueError("Polyline.at takes finite distances")
            u = self._wrap(u)
            xs: _F = np.interp(u, self._cum, self._loop[:, 0])
            ys: _F = np.interp(u, self._cum, self._loop[:, 1])
            return np.stack([xs, ys], axis=-1)
        v = self._wrap1(num(d, "Polyline.at"))
        x = float(np.interp(v, self._cum, self._loop[:, 0]))
        y = float(np.interp(v, self._cum, self._loop[:, 1]))
        return Vec(x, y)

    def tangent(self, d: Num) -> Vec:
        """The unit direction of the segment at arc length `d` (clamped or wrapped as in at());
        at a vertex, the outgoing segment's, and at the end of an open line the last one's."""
        u = self._wrap1(num(d, "Polyline.tangent"))
        i = int(np.searchsorted(self._cum, u, side="right")) - 1
        i = min(max(i, 0), len(self._seg) - 1)
        ends: list[list[float]] = self._loop[i : i + 2].tolist()
        (ax, ay), (bx, by) = ends
        n = math.hypot(bx - ax, by - ay)
        return Vec((bx - ax) / n, (by - ay) / n)

    def resample(self, step: Num) -> "Polyline":
        """Points every `step` of arc length from the start, plus the end point of an open line.

        Raises ValueError unless step > 0, or when a closed line would keep fewer than 2 points.
        """
        h = num(step, "Polyline.resample")
        if h <= 0:
            raise ValueError(f"resample takes a step above 0, got {step!r}")
        u = np.arange(0.0, self.length, h)
        pts = self.at(u)
        if not self.closed:
            pts = np.vstack([pts, self._loop[-1:]])
        elif len(u) < 2:
            raise ValueError(f"a step of {h:g} leaves fewer than 2 points on {self!r}")
        return Polyline(pts, closed=self.closed)

    def offset(self, dist: Num) -> "Polyline":
        """Each vertex moved by `dist` along the unit bisector of its segments' normals (an end
        vertex along its one segment's normal); positive is to the right of the direction of
        travel on screen. The point count is kept unless moved points coincide."""
        k = num(dist, "Polyline.offset")
        return Polyline(self.pts + k * _normals(self.pts, self.closed), closed=self.closed)


def spline_points(pts: ArrayLike, n: int, *, closed: bool = False) -> _F:
    """Points on the Catmull-Rom curve P().spline(pts, closed=closed) draws: `n` per segment
    at t = k / n, plus the last point of an open curve. Fewer than 3 points come back as
    they are.

    Raises ValueError for n < 1 or points not of shape (N, 2).
    """
    per = _count(n, "spline_points n", 1)
    p = _points(pts, "spline_points")
    m = len(p)
    if m < 3:
        return p.copy()
    i = np.arange(m if closed else m - 1)
    if closed:
        p0, p3 = p[(i - 1) % m], p[(i + 2) % m]
    else:
        p0, p3 = p[np.maximum(i - 1, 0)], p[np.minimum(i + 2, m - 1)]
    p1, p2 = p[i], p[(i + 1) % m]
    k = 1.0 / 6
    c1, c2 = p1 + (p2 - p0) * k, p2 - (p3 - p1) * k
    t = (np.arange(per) / per)[None, :, None]
    u = 1 - t
    curve = (
        u**3 * p1[:, None]
        + 3 * u * u * t * c1[:, None]
        + 3 * u * t * t * c2[:, None]
        + t**3 * p2[:, None]
    )
    out = curve.reshape(-1, 2)
    return out if closed else np.vstack([out, p[-1:]])


def bezier_points(ctrl: ArrayLike, n: int) -> _F:
    """`n` + 1 points at t = linspace(0, 1, n + 1) on the quadratic (3 control points) or
    cubic (4) Bézier curve.

    Raises ValueError for another number of control points or n < 1.
    """
    per = _count(n, "bezier_points n", 1)
    c = _points(ctrl, "bezier_points")
    t = np.linspace(0, 1, per + 1)[:, None]
    p0, p1, p2, p3 = c[0:1], c[1:2], c[2:3], c[3:4]
    if len(c) == 3:
        return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2
    if len(c) == 4:
        return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3
    raise ValueError(f"bezier_points takes 3 or 4 control points, got {len(c)}")


def ribbon(pts: ArrayLike, width: Num | ArrayLike) -> _F:
    """The closed outline of a stroke of varying width along the open polyline `pts`: its
    vertices offset by +width / 2 along Polyline.offset's normals, in order, then by
    -width / 2, in reverse, shape (2N, 2). `width` is one number or one per vertex.

    Raises ValueError for fewer than 2 points, consecutive repeated points, a width array of
    another length, or non-finite values.
    """
    p = _points(pts, "ribbon")
    if len(p) < 2:
        raise ValueError(f"ribbon takes at least 2 points, got {len(p)}")
    if bool(np.any(np.all(p[1:] == p[:-1], axis=1))):
        raise ValueError("ribbon takes points without consecutive repeats")
    w = np.asarray(width, dtype=np.float64)
    if w.ndim > 1 or (w.ndim == 1 and len(w) != len(p)):
        raise ValueError(f"ribbon takes one width or {len(p)}, got shape {w.shape}")
    if not bool(np.isfinite(w).all()):
        raise ValueError("ribbon takes finite widths")
    half = (w / 2).reshape(-1, 1)
    nrm = _normals(p, closed=False)
    return np.vstack([p + nrm * half, (p - nrm * half)[::-1]])


@overload
def hatch(region: BaseGeometry, pitch: Num, *, deg: Num, offset: Num = 0.0) -> list[_F]: ...
@overload
def hatch(region: BaseGeometry, pitch: Num, *, rad: Num, offset: Num = 0.0) -> list[_F]: ...
@overload
def hatch(region: BaseGeometry, pitch: Num, *, bearing: Num, offset: Num = 0.0) -> list[_F]: ...
def hatch(
    region: BaseGeometry,
    pitch: Num,
    *,
    deg: Num | None = None,
    rad: Num | None = None,
    bearing: Num | None = None,
    offset: Num = 0.0,
) -> list[_F]:
    """Parallel lines in the given direction, `pitch` apart measured across them, clipped to
    `region`: the line through the centre of region.bounds shifted across by offset + k * pitch
    for every k that reaches the region.

    Each piece is a (2, 2) segment running in the line's direction; pieces come ordered by k,
    then along the line. Raises TypeError unless exactly one angle keyword is given, and
    ValueError unless pitch > 0.
    """
    a = angle(deg, rad, bearing, "hatch")
    h = num(pitch, "hatch pitch")
    if h <= 0:
        raise ValueError(f"hatch takes a pitch above 0, got {pitch!r}")
    o = num(offset, "hatch offset")
    if region.is_empty:
        return []
    x0, y0, x1, y1 = region.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = math.hypot(x1 - x0, y1 - y0) / 2
    ux, uy = math.cos(a), math.sin(a)
    ext = r + h
    out: list[_F] = []
    for k in range(math.ceil((-r - o) / h), math.floor((r - o) / h) + 1):
        px, py = cx - uy * (o + k * h), cy + ux * (o + k * h)
        line = LineString([(px - ux * ext, py - uy * ext), (px + ux * ext, py + uy * ext)])
        pieces: list[tuple[float, _F]] = []
        for g in parts(line.intersection(region)):
            if not isinstance(g, LineString):
                continue
            xy = np.asarray(g.coords, dtype=np.float64)[:, :2]
            seg = xy[[0, -1]]
            ta, tb = (float(v) for v in (seg - (px, py)) @ (ux, uy))
            if ta == tb:
                continue
            pieces.append((min(ta, tb), seg if ta < tb else seg[::-1].copy()))
        pieces.sort(key=lambda piece: piece[0])
        out += [seg for _, seg in pieces]
    return out


@overload
def ngon(c: Point, r: Num, n: int, *, deg: Num, inner: Num | None = None) -> _F: ...
@overload
def ngon(c: Point, r: Num, n: int, *, rad: Num, inner: Num | None = None) -> _F: ...
@overload
def ngon(c: Point, r: Num, n: int, *, bearing: Num, inner: Num | None = None) -> _F: ...
def ngon(
    c: Point,
    r: Num,
    n: int,
    *,
    deg: Num | None = None,
    rad: Num | None = None,
    bearing: Num | None = None,
    inner: Num | None = None,
) -> _F:
    """The vertices of a regular n-gon around `c`, the first at the given angle, shape (n, 2);
    with `inner`, a star of 2n vertices alternating radius r and `inner`.

    Raises TypeError unless exactly one angle keyword is given, and ValueError for n < 3.
    """
    return ngon_vertices(c, r, n, angle(deg, rad, bearing, "ngon"), inner)


def _box(rect: Rect, what: str) -> tuple[float, float, float, float]:
    x, y, w, h = rect
    return num(x, what), num(y, what), num(w, what), num(h, what)


def _rng(rng: object, what: str) -> random.Random:
    if not isinstance(rng, random.Random):
        raise TypeError(f"{what} takes a random.Random from s.rng(key), got {rng!r}")
    return rng


def scatter(
    n: int,
    rect: Rect,
    rng: random.Random,
    *,
    min_dist: Num = 0.0,
    accept: Callable[[Vec], bool] | None = None,
    tries: int = 30,
) -> _F:
    """Up to `n` points thrown at random into `rect`.

    Draws up to n * tries candidates (rng.uniform(x, x1), rng.uniform(y, y1)), x first, and
    keeps each unless `accept` returns False for it or a kept point lies closer than
    `min_dist`; stops at `n` kept points, so it may return fewer. Raises ValueError for n < 0,
    tries < 1 or a negative min_dist, and TypeError when `rng` is not a random.Random.
    """
    want = _count(n, "scatter n", 0)
    per = _count(tries, "scatter tries", 1)
    x0, y0, w, h = _box(rect, "scatter rect")
    r = _rng(rng, "scatter")
    md = num(min_dist, "scatter min_dist")
    if md < 0:
        raise ValueError(f"scatter takes min_dist >= 0, got {min_dist!r}")
    kept: list[tuple[float, float]] = []
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for _ in range(want * per):
        if len(kept) >= want:
            break
        x, y = r.uniform(x0, x0 + w), r.uniform(y0, y0 + h)
        if md > 0:
            gx, gy = math.floor(x / md), math.floor(y / md)
            near = (
                q for i in (-1, 0, 1) for j in (-1, 0, 1) for q in grid.get((gx + i, gy + j), ())
            )
            if any((qx - x) ** 2 + (qy - y) ** 2 < md * md for qx, qy in near):
                continue
        if accept is not None and not accept(Vec(x, y)):
            continue
        kept.append((x, y))
        if md > 0:
            grid.setdefault((math.floor(x / md), math.floor(y / md)), []).append((x, y))
    return np.array(kept, dtype=np.float64).reshape(-1, 2)


def poisson_disk(rect: Rect, radius: Num, rng: random.Random, *, k: int = 30) -> _F:
    """Bridson Poisson-disk samples at least `radius` apart inside `rect`, in the order found.

    Draws from `rng` exactly as v1 did, so poisson_disk(Rect(x0, y0, w, h), radius, s.rng(n),
    k=k) returns v1's poisson_disk(rng(n), w, h, radius, k, x0, y0). Raises ValueError unless
    radius > 0 and k >= 1, and TypeError when `rng` is not a random.Random.
    """
    x0, y0, width, height = _box(rect, "poisson_disk rect")
    rad = num(radius, "poisson_disk radius")
    if rad <= 0:
        raise ValueError(f"poisson_disk takes a radius above 0, got {radius!r}")
    tries = _count(k, "poisson_disk k", 1)
    r = _rng(rng, "poisson_disk")
    cs = rad / math.sqrt(2)
    gw, gh = int(width / cs) + 1, int(height / cs) + 1
    grid: list[list[tuple[float, float] | None]] = [[None] * gw for _ in range(gh)]
    first = (r.uniform(0, width), r.uniform(0, height))
    out, active = [first], [first]
    grid[int(first[1] / cs)][int(first[0] / cs)] = first
    while len(active) > 0:
        idx = r.randrange(len(active))
        px, py = active[idx]
        for _ in range(tries):
            a, d = r.uniform(0, 2 * math.pi), r.uniform(rad, 2 * rad)
            x, y = px + d * math.cos(a), py + d * math.sin(a)
            if not (0 <= x < width and 0 <= y < height):
                continue
            gx, gy = int(x / cs), int(y / cs)
            ok = True
            for yy in range(max(0, gy - 2), min(gh, gy + 3)):
                for xx in range(max(0, gx - 2), min(gw, gx + 3)):
                    q = grid[yy][xx]
                    if q is not None and (q[0] - x) ** 2 + (q[1] - y) ** 2 < rad * rad:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                grid[gy][gx] = (x, y)
                out.append((x, y))
                active.append((x, y))
                break
        else:
            active.pop(idx)
    return np.array([(x + x0, y + y0) for x, y in out], dtype=np.float64)


def parts(g: BaseGeometry) -> list[BaseGeometry]:
    """The single-part geometries of `g`: Multi* and GeometryCollection flattened
    recursively, in order, with empty parts dropped."""
    if g.is_empty:
        return []
    if isinstance(g, BaseMultipartGeometry):
        return [q for sub in g.geoms for q in parts(sub)]
    return [g]

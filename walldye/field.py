"""Scalar fields on grids: noise, sample lattices, radial falloffs, iso-lines and runs.

Fields are (rows, cols) float64 arrays; everything here works element-wise on numpy arrays.
"""

import math
from collections.abc import Callable
from typing import cast, overload

import numpy as np
from numpy.typing import ArrayLike, NDArray
from skimage.measure import approximate_polygon, find_contours

from ._noise import Noise
from ._vec import NUM_TYPES, Num, Point, Rect, num, point

__all__ = [
    "Noise",
    "cells",
    "falloff",
    "gauss",
    "iso_lines",
    "noise_grid",
    "runs",
    "sample_field",
]

type _F = NDArray[np.float64]
type _I = NDArray[np.int64]


def _count(n: object, what: str, least: int) -> int:
    """`n` as an int of at least `least`. Raises TypeError for a non-int (or bool) and
    ValueError below `least`."""
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)):
        raise TypeError(f"{what} takes an int, got {n!r}")
    v = int(n)
    if v < least:
        raise ValueError(f"{what} takes an int >= {least}, got {n!r}")
    return v


def _positive(v: object, what: str) -> float:
    f = num(v, what)
    if f <= 0:
        raise ValueError(f"{what} takes a number above 0, got {v!r}")
    return f


def _dot(vx: _F, vy: _F, ix: _I, iy: _I, dx: _F, dy: _F) -> _F:
    """The lattice gradients at (ix, iy) dotted with the offsets (dx, dy)."""
    gx: _F = vx[iy, ix]
    gy: _F = vy[iy, ix]
    return gx * dx + gy * dy


def noise_grid(
    cols: int,
    rows: int,
    scale: Num,
    rng: np.random.Generator,
    *,
    octaves: int = 1,
    gain: Num = 0.5,
) -> _F:
    """A (rows, cols) fBm Perlin field roughly within [-1, 1]; `scale` is the base feature
    size in cells, and each further octave is twice as fine and `gain` times as strong.

    Draws from `rng` in the order tests/python/fixtures/v1_pins pins, so designs keep the fields
    they were tuned on. Raises ValueError for sizes or octaves below 1 or a scale not above 0, and
    TypeError when `rng` is not a numpy Generator.
    """
    nc, nr = _count(cols, "noise_grid cols", 1), _count(rows, "noise_grid rows", 1)
    sc = _positive(scale, "noise_grid scale")
    n_oct = _count(octaves, "noise_grid octaves", 1)
    g = num(gain, "noise_grid gain")
    if not isinstance(rng, np.random.Generator):
        raise TypeError(f"noise_grid takes a numpy Generator from s.np_rng(key), got {rng!r}")
    out: _F = np.zeros((nr, nc))
    amp, norm = 1.0, 0.0
    for o in range(n_oct):
        s = sc / 2.0**o
        gx, gy = int(nc / s) + 2, int(nr / s) + 2
        ang: _F = rng.uniform(0, 2 * np.pi, (gy, gx))
        # The random offset can push x0 + 1 one past the lattice; wrap one extra cell.
        vx: _F = np.pad(np.cos(ang), ((0, 1), (0, 1)), mode="wrap")
        vy: _F = np.pad(np.sin(ang), ((0, 1), (0, 1)), mode="wrap")
        x: _F = np.arange(nc) / s + rng.uniform(0, 1)
        y: _F = np.arange(nr) / s + rng.uniform(0, 1)
        xx, yy = np.meshgrid(x, y)
        x0: _I = xx.astype(int)
        y0: _I = yy.astype(int)
        fx, fy = xx - x0, yy - y0
        u = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
        v = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
        d00 = _dot(vx, vy, x0, y0, fx, fy)
        d01 = _dot(vx, vy, x0, y0 + 1, fx, fy - 1)
        n0 = d00 + u * (_dot(vx, vy, x0 + 1, y0, fx - 1, fy) - d00)
        n1 = d01 + u * (_dot(vx, vy, x0 + 1, y0 + 1, fx - 1, fy - 1) - d01)
        out += amp * (n0 + v * (n1 - n0)) * 1.41
        norm += amp
        amp *= g
    return out / norm


def cells(rect: Rect, cell: Num) -> tuple[_F, _F]:
    """The centers of the whole `cell`-sized cells covering `rect` from its top-left: xs and
    ys, both (rows, cols) with rows = int(h // cell) and cols = int(w // cell), where
    xs[j, i] = x + (i + 0.5) * cell and ys[j, i] = y + (j + 0.5) * cell.

    Raises ValueError unless cell > 0.
    """
    c = _positive(cell, "cells cell")
    x, y, w, h = (num(v, "cells rect") for v in rect)
    cols, rows = int(w // c), int(h // c)
    xs = x + (np.arange(cols) + 0.5) * c
    ys = y + (np.arange(rows) + 0.5) * c
    gx, gy = np.meshgrid(xs, ys)
    return gx.astype(np.float64), gy.astype(np.float64)


def _scalar(v: object) -> bool:
    """Whether `v` takes the scalar path; bools do, so that num() rejects them."""
    return isinstance(v, NUM_TYPES)


@overload
def falloff(d: Num, r: Num, power: Num = 1.0) -> float: ...
@overload
def falloff(d: ArrayLike, r: Num, power: Num = 1.0) -> _F: ...
def falloff(d: ArrayLike, r: Num, power: Num = 1.0) -> float | _F:
    """clip(1 - d / r, 0, 1) ** power: 1 at distance 0, fading to 0 at `r` and beyond. A
    float for a number, element-wise float64 for an array.

    Raises ValueError unless r > 0.
    """
    rr = _positive(r, "falloff r")
    k = num(power, "falloff power")
    if _scalar(d):
        v = 1 - num(d, "falloff d") / rr
        t = 0.0 if v < 0 else min(v, 1.0)
        return math.pow(t, k)
    a = np.asarray(d, dtype=np.float64)
    out: _F = np.clip(1 - a / rr, 0, 1) ** k
    return out


@overload
def gauss(d: Num, sigma: Num) -> float: ...
@overload
def gauss(d: ArrayLike, sigma: Num) -> _F: ...
def gauss(d: ArrayLike, sigma: Num) -> float | _F:
    """exp(-(d / sigma) ** 2), without the usual factor of 2. A float for a number,
    element-wise float64 for an array.

    Raises ValueError unless sigma > 0.
    """
    sg = _positive(sigma, "gauss sigma")
    if _scalar(d):
        return math.exp(-((num(d, "gauss d") / sg) ** 2))
    a = np.asarray(d, dtype=np.float64)
    out: _F = np.exp(-((a / sg) ** 2))
    return out


def iso_lines(
    field: ArrayLike,
    level: Num,
    *,
    cell: Num = 1.0,
    origin: Point = (0.0, 0.0),
    simplify: Num = 0.0,
) -> list[_F]:
    """The lines where the (rows, cols) `field` crosses `level` (skimage's marching squares),
    in canvas coordinates origin + (col, row) * cell, each (N, 2).

    Closed lines repeat their first point at the end. With simplify > 0, each line is
    reduced by Douglas-Peucker to that tolerance in canvas units. Raises ValueError for a
    field that is not 2-D with at least 2 rows and columns, a cell not above 0, or a negative
    simplify.
    """
    f = np.asarray(field, dtype=np.float64)
    if f.ndim != 2 or f.shape[0] < 2 or f.shape[1] < 2:
        raise ValueError(f"iso_lines takes a 2-D field of at least 2 x 2, got shape {f.shape}")
    lv = num(level, "iso_lines level")
    c = _positive(cell, "iso_lines cell")
    ox, oy = point(origin, "iso_lines origin")
    tol = num(simplify, "iso_lines simplify")
    if tol < 0:
        raise ValueError(f"iso_lines takes simplify >= 0, got {simplify!r}")
    out: list[_F] = []
    for rc in cast("list[_F]", find_contours(f, lv)):
        xy = np.stack([ox + rc[:, 1] * c, oy + rc[:, 0] * c], axis=1)
        if tol > 0:
            xy = cast("_F", approximate_polygon(xy, tol))
        out.append(xy)
    return out


def runs(mask: ArrayLike) -> list[tuple[int, int]]:
    """The half-open (start, stop) index ranges of consecutive true values in the 1-D boolean
    `mask`, in order.

    Raises TypeError for a non-boolean array and ValueError for one that is not 1-D.
    """
    m = np.asarray(mask)
    if m.dtype != np.bool_:
        raise TypeError(f"runs takes a boolean array, got dtype {m.dtype}")
    if m.ndim != 1:
        raise ValueError(f"runs takes a 1-D array, got shape {m.shape}")
    edges: list[int] = np.flatnonzero(np.diff(np.concatenate([[0], m.astype(int), [0]]))).tolist()
    return list(zip(edges[::2], edges[1::2], strict=True))


def sample_field(fn: Callable[[_I, _I], ArrayLike], cols: int, rows: int) -> _F:
    """`fn(i, j)` called once with the integer lattice index arrays of shape (rows + 1,
    cols + 1), i the column and j the row index; the result as float64 of that shape, the
    corner lattice iso_lines expects.

    Raises ValueError for sizes below 1 or a result that does not broadcast to the shape.
    """
    nc, nr = _count(cols, "sample_field cols", 1), _count(rows, "sample_field rows", 1)
    j, i = np.indices((nr + 1, nc + 1), dtype=np.int64)
    out = np.asarray(fn(i, j), dtype=np.float64)
    return np.broadcast_to(out, (nr + 1, nc + 1)).copy()

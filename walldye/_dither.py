"""Dithering: ordered threshold masks and error diffusion, on plain arrays."""

import collections
import operator
import pickle
from collections.abc import Mapping
from typing import Final, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ._vec import Num, count, np_generator, positive

type DitherMethod = Literal[
    "bayer",
    "clustered",
    "bluenoise",
    "lines",
    "random",
    "fs",
    "atkinson",
    "jarvis",
    "stucki",
    "burkes",
    "sierra",
    "sierra-lite",
    "riemersma",
]
type _F = NDArray[np.float64]
type _I = NDArray[np.int64]

_ORDERED: Final = ("bayer", "clustered", "bluenoise", "lines", "random")

# Error-diffusion taps (dx, dy, weight) and their divisors; atkinson drops a quarter of the
# error on purpose.
_DIFFUSION: Final[dict[str, tuple[tuple[tuple[int, int, int], ...], int]]] = {
    "fs": (((1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)), 16),
    "atkinson": (((1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1)), 8),
    "jarvis": (
        (
            (1, 0, 7),
            (2, 0, 5),
            (-2, 1, 3),
            (-1, 1, 5),
            (0, 1, 7),
            (1, 1, 5),
            (2, 1, 3),
            (-2, 2, 1),
            (-1, 2, 3),
            (0, 2, 5),
            (1, 2, 3),
            (2, 2, 1),
        ),
        48,
    ),
    "stucki": (
        (
            (1, 0, 8),
            (2, 0, 4),
            (-2, 1, 2),
            (-1, 1, 4),
            (0, 1, 8),
            (1, 1, 4),
            (2, 1, 2),
            (-2, 2, 1),
            (-1, 2, 2),
            (0, 2, 4),
            (1, 2, 2),
            (2, 2, 1),
        ),
        42,
    ),
    "burkes": (((1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2)), 32),
    "sierra": (
        (
            (1, 0, 5),
            (2, 0, 3),
            (-2, 1, 2),
            (-1, 1, 4),
            (0, 1, 5),
            (1, 1, 4),
            (2, 1, 2),
            (-1, 2, 2),
            (0, 2, 3),
            (1, 2, 2),
        ),
        32,
    ),
    "sierra-lite": (((1, 0, 2), (-1, 1, 1), (0, 1, 1)), 4),
}

# 8x8 clustered-dot threshold order: dots grow from the center, like a print halftone screen.
_CLUSTERED8: Final = (
    (24, 10, 12, 26, 35, 47, 49, 37),
    (8, 0, 2, 14, 45, 59, 61, 51),
    (22, 6, 4, 16, 43, 57, 63, 53),
    (30, 20, 18, 28, 33, 41, 55, 39),
    (34, 46, 48, 36, 25, 11, 13, 27),
    (44, 58, 60, 50, 9, 1, 3, 15),
    (42, 56, 62, 52, 23, 7, 5, 17),
    (32, 40, 54, 38, 31, 21, 19, 29),
)

# (n, sigma, pickled generator state on entry) -> (mask, generator state on exit), the most
# recent _BLUE_SIZE in a process
_BLUE: Final[collections.OrderedDict[tuple[int, float, bytes], tuple[_F, Mapping[str, object]]]] = (
    collections.OrderedDict()
)
_BLUE_SIZE: Final = 32


def bayer(n: int) -> _F:
    """The (n, n) Bayer ordered-dither threshold matrix, values (v + 0.5) / n**2.

    Raises ValueError unless n is a power of two of at least 2.
    """
    size = count(n, "bayer n", 2)
    if size & (size - 1) != 0:
        raise ValueError(f"bayer takes a power of two, got {n!r}")
    m: _I = np.array([[0, 2], [3, 1]], dtype=np.int64)
    while len(m) < size:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / (size * size)


def blue_noise(n: int, rng: np.random.Generator, *, sigma: Num = 1.5) -> _F:
    """An (n, n) void-and-cluster blue-noise threshold mask, values (rank + 0.5) / n**2,
    drawing from `rng` in the order tests/python/fixtures/v1_pins pins.

    Results are cached by n, sigma and the generator's state on entry; a cached call also
    leaves the generator in the state an uncached one would. Raises ValueError for n < 1 or
    a sigma not above 0, and TypeError when `rng` is not a numpy Generator.
    """
    size = count(n, "blue_noise n", 1)
    sg = positive(sigma, "blue_noise sigma")
    rng = np_generator(rng, "blue_noise")
    key = (size, sg, pickle.dumps(rng.bit_generator.state))
    hit = _BLUE.get(key)
    if hit is None:
        hit = _BLUE[key] = (_void_and_cluster(size, rng, sg), rng.bit_generator.state)
        if len(_BLUE) > _BLUE_SIZE:
            _BLUE.popitem(last=False)
    else:
        _BLUE.move_to_end(key)
        rng.bit_generator.state = hit[1]
    return hit[0].copy()


def _void_and_cluster(n: int, r: np.random.Generator, sigma: float) -> _F:
    """Ulichney's void-and-cluster ranking of an n x n torus; tests pin its steps and draws."""
    d: _I = np.minimum(np.arange(n), n - np.arange(n))
    kern: _F = np.exp(-(d[:, None] ** 2 + d[None, :] ** 2) / (2 * sigma * sigma))
    kf = np.fft.fft2(kern)

    def energy(b: _F) -> _F:
        out: _F = np.real(np.fft.ifft2(np.fft.fft2(b) * kf))
        return out

    def bump(e: _F, idx: int, sign: int) -> None:
        y, x = divmod(idx, n)
        e += sign * np.roll(np.roll(kern, y, 0), x, 1)

    b: _F = (r.random((n, n)) < 0.1).astype(np.float64)
    e = energy(b)
    while True:
        c = int(np.argmax(np.where(b > 0, e, -np.inf)))
        b.flat[c] = 0
        bump(e, c, -1)
        v = int(np.argmin(np.where(b > 0, np.inf, e)))
        if v == c:
            b.flat[c] = 1
            bump(e, c, 1)
            break
        b.flat[v] = 1
        bump(e, v, 1)
    proto, ones = b.copy(), int(b.sum())
    rank: _F = np.zeros(n * n)
    e = energy(b)
    for k in range(ones - 1, -1, -1):
        c = int(np.argmax(np.where(b > 0, e, -np.inf)))
        b.flat[c] = 0
        bump(e, c, -1)
        rank[c] = k
    b = proto.copy()
    e = energy(b)
    for k in range(ones, n * n):
        v = int(np.argmin(np.where(b > 0, np.inf, e)))
        b.flat[v] = 1
        bump(e, v, 1)
        rank[v] = k
    return (rank.reshape(n, n) + 0.5) / (n * n)


def threshold_matrix(
    method: Literal["bayer", "clustered", "bluenoise", "lines", "random"],
    size: int = 4,
    rng: np.random.Generator | None = None,
) -> _F:
    """An ordered-dither threshold mask with values in (0, 1).

    "bayer" is bayer(size); "clustered" the 8x8 clustered-dot screen; "bluenoise"
    blue_noise(max(size, 64), rng); "lines" a horizontal line screen `size` cells in pitch;
    "random" rng.random((k, k)) with k = max(size, 64). Raises ValueError for another method,
    and for "bluenoise" or "random" without `rng`.
    """
    k = count(size, "threshold_matrix size", 1)
    if method == "bayer":
        return bayer(k)
    if method == "clustered":
        return (np.array(_CLUSTERED8, dtype=np.float64) + 0.5) / 64
    if method == "lines":
        return np.repeat((np.arange(k)[:, None] + 0.5) / k, k, axis=1)
    if method in ("bluenoise", "random"):
        if rng is None:
            raise ValueError(f"the {method} mask needs rng=s.np_rng(key)")
        if method == "bluenoise":
            return blue_noise(max(k, 64), rng)
        out: _F = rng.random((max(k, 64), max(k, 64)))
        return out
    raise ValueError(f"threshold_matrix takes one of {', '.join(_ORDERED)}, got {method!r}")


def _hilbert(order: int, cols: int, rows: int) -> list[tuple[int, int]]:
    """The cells of a 2**order square Hilbert curve in curve order, those outside `cols` x
    `rows` left out."""
    n = 1 << order
    t: _I = np.arange(n * n, dtype=np.int64)
    x: _I = np.zeros_like(t)
    y: _I = np.zeros_like(t)
    s = 1
    while s < n:
        rx: _I = 1 & (t // 2)
        ry: _I = 1 & (t ^ rx)
        turn: NDArray[np.bool_] = ry == 0
        flip: NDArray[np.bool_] = turn & (rx == 1)
        x[flip], y[flip] = s - 1 - x[flip], s - 1 - y[flip]
        x[turn], y[turn] = y[turn], x[turn]
        x += s * rx
        y += s * ry
        t //= 4
        s *= 2
    keep = (x < cols) & (y < rows)
    return list(zip(x[keep].tolist(), y[keep].tolist(), strict=True))


def dither(
    field: ArrayLike,
    levels: int,
    *,
    method: DitherMethod = "bayer",
    matrix: int = 4,
    rng: np.random.Generator | None = None,
    serpentine: bool = False,
) -> _I:
    """Quantize the (rows, cols) `field`, clamped to [0, 1], to indices 0 .. levels - 1 of the
    same shape.

    Ordered methods threshold against threshold_matrix(method, matrix, rng): "bayer" (a
    crisp crosshatch; matrix 2, 4, 8 or 16), "clustered" (halftone dots), "bluenoise" (even
    grain), "lines" (a line screen matrix cells in pitch) and "random" (white-noise grain).
    Error diffusion: "fs", "atkinson" (drops a quarter of the error, for more contrast),
    "jarvis", "stucki", "burkes", "sierra" and "sierra-lite", with `serpentine` alternating
    the row direction; "riemersma" diffuses along a Hilbert curve. Raises ValueError for
    fewer than 2 levels, a field that is not 2-D or not finite, an unknown method, or
    "bluenoise" or "random" without `rng`.
    """
    f = np.asarray(field, dtype=np.float64)
    if f.ndim != 2:
        raise ValueError(f"dither takes a (rows, cols) field, got shape {f.shape}")
    if not bool(np.isfinite(f).all()):
        raise ValueError("dither takes a finite field")
    n = count(levels, "dither levels", 2) - 1
    rows, cols = int(f.shape[0]), int(f.shape[1])
    if method in _ORDERED:
        m = threshold_matrix(method, matrix, rng)
        k = len(m)
        thr: _F = m[np.arange(rows)[:, None] % k, np.arange(cols)[None, :] % k]
        q: _F = np.clip(f, 0, 1) * n
        b: _F = np.floor(q)
        up: NDArray[np.bool_] = q - b > thr
        out_q: _F = np.minimum(n, b + up)
        return out_q.astype(np.int64)
    if method != "riemersma" and method not in _DIFFUSION:
        raise ValueError(f"unknown dither method {method!r}")
    buf: list[list[float]] = [[_clamp01(v) * n for v in row] for row in f.tolist()]
    out = [[0] * cols for _ in range(rows)]
    if method == "riemersma":
        steps, ratio = 16, 1 / 16
        weights = [ratio ** (1 - i / (steps - 1)) for i in range(steps)]
        total = sum(weights)
        hist = collections.deque([0.0] * steps, maxlen=steps)
        # sum() over floats compensates its rounding, so keep it rather than a running total
        for x, y in _hilbert(max(cols, rows).bit_length(), cols, rows):
            v = buf[y][x] + sum(map(operator.mul, hist, weights)) / total * 2
            r = round(v)
            new = 0 if r < 0 else min(r, n)
            out[y][x] = new
            hist.append(buf[y][x] - new)
        return np.array(out, dtype=np.int64)
    taps, div = _DIFFUSION[method]
    for j in range(rows):
        rev = serpentine and j % 2 == 1
        # the taps that land inside the field's rows, with their target row resolved; the
        # same taps in the same order as a per-pixel check, so the sums round the same
        live = [(-dx if rev else dx, buf[j + dy], wgt) for dx, dy, wgt in taps if j + dy < rows]
        row, orow = buf[j], out[j]
        for i in range(cols - 1, -1, -1) if rev else range(cols):
            old = row[i]
            r = round(old)
            new = 0 if r < 0 else min(r, n)
            orow[i] = new
            err = old - new
            for dx, target, wgt in live:
                x = i + dx
                if 0 <= x < cols:
                    target[x] += err * wgt / div
    return np.array(out, dtype=np.int64)


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else min(v, 1.0)

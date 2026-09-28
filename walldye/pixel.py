"""Pixel work: index grids drawn as merged runs, dithering, sprites and bitmap text.

Everything draws through Canvas.pixel_path, so each path is marked for crisp export and its
grid origin is recorded on the document.
"""

import collections
import functools
import operator
import pickle
from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from typing import Final, Literal, Unpack, final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ._canvas import Canvas, Paint, Style
from ._path import Path
from ._vec import Num, Point, num, point
from .font import FONTS

__all__ = [
    "DitherMethod",
    "Font",
    "Pixels",
    "bayer",
    "blue_noise",
    "dither",
    "glyph",
    "glyphs",
    "grid_runs",
    "sprite",
    "text_width",
    "threshold_matrix",
]

type Font = Literal["5x8", "8x16"]
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

# Error-diffusion taps (dx, dy, weight) and their divisors; atkinson deliberately drops a
# quarter of the error, which gives its high-contrast look.
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

# 8x8 clustered-dot threshold order: dots grow from the centre, like a print halftone screen.
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

# (n, sigma, pickled generator state on entry) -> (mask, generator state on exit)
_BLUE: Final[dict[tuple[int, float, bytes], tuple[_F, Mapping[str, object]]]] = {}


def _count(n: object, what: str, least: int) -> int:
    """`n` as an int of at least `least`. Raises TypeError for a non-int (or bool) and
    ValueError below `least`."""
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)):
        raise TypeError(f"{what} takes an int, got {n!r}")
    v = int(n)
    if v < least:
        raise ValueError(f"{what} takes an int >= {least}, got {n!r}")
    return v


def _int(n: object, what: str) -> int:
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)):
        raise TypeError(f"{what} takes an int, got {n!r}")
    return int(n)


def _positive(v: object, what: str) -> float:
    f = num(v, what)
    if f <= 0:
        raise ValueError(f"{what} takes a number above 0, got {v!r}")
    return f


def _index(v: object, size: int, what: str) -> int:
    """`v` as a palette index. Raises TypeError for a non-int and IndexError outside
    range(size)."""
    i = _int(v, what)
    if not 0 <= i < size:
        raise IndexError(f"{what} {i} is outside the palette (0..{size - 1})")
    return i


def _rows(art: object, what: str) -> list[str]:
    """Rows of pixel art: a str stripped of leading and trailing newlines and split on them,
    or a sequence of str. Raises TypeError otherwise."""
    if isinstance(art, str):
        return art.strip("\n").split("\n")
    if not isinstance(art, Sequence):
        raise TypeError(f"{what} takes a str or a sequence of str rows, got {art!r}")
    items: Sequence[object] = art
    out: list[str] = []
    for row in items:
        if not isinstance(row, str):
            raise TypeError(f"{what} rows are str, got {row!r}")
        out.append(row)
    return out


def _grid(grid: ArrayLike, what: str) -> _I:
    a = np.asarray(grid)
    if a.dtype.kind not in "iu":
        raise TypeError(
            f"{what} takes an integer index grid, got dtype {a.dtype}; mark empty cells with"
            " an index whose palette entry is None"
        )
    if a.ndim != 2:
        raise ValueError(f"{what} takes a (rows, cols) grid, got shape {a.shape}")
    return a.astype(np.int64)


def grid_runs(
    s: Canvas,
    grid: ArrayLike,
    palette: Sequence[Paint | None],
    cell: Num,
    origin: Point = (0.0, 0.0),
    *,
    skip: int | None = 0,
    **style: Unpack[Style],
) -> None:
    """Draw the (rows, cols) index `grid` as merged horizontal runs of `cell`-sized squares
    with (0, 0) at `origin`: one pixel path per palette index, in ascending index order.

    Cells equal to `skip` (None draws every index) and indices whose palette entry is None
    are not drawn. Raises TypeError for a grid that is not integer, ValueError for one that
    is not 2-D or a cell not above 0, and IndexError for a drawn index outside the palette.
    """
    g = _grid(grid, "grid_runs")
    c = _positive(cell, "grid_runs cell")
    ox, oy = point(origin, "grid_runs origin")
    sk = None if skip is None else _int(skip, "grid_runs skip")
    pal = tuple(palette)
    if g.size == 0:
        return
    cols = int(g.shape[1])
    start: NDArray[np.bool_] = np.ones(g.shape, dtype=np.bool_)
    start[:, 1:] = g[:, 1:] != g[:, :-1]
    nz: tuple[NDArray[np.intp], ...] = np.nonzero(start)
    js: _I = nz[0].astype(np.int64)
    xs: _I = nz[1].astype(np.int64)
    stops = np.full(len(xs), cols, dtype=np.int64)
    stops[:-1] = np.where(js[1:] == js[:-1], xs[1:], cols)
    vals: _I = g[js, xs]
    keep = np.ones(len(vals), dtype=bool) if sk is None else vals != sk
    drawn: _I = vals[keep]
    lo, hi = (int(drawn.min()), int(drawn.max())) if len(drawn) > 0 else (0, 0)
    if lo < 0 or hi >= len(pal):
        bad = lo if lo < 0 else hi
        raise IndexError(f"grid_runs index {bad} is outside the palette (0..{len(pal) - 1})")
    paths: dict[int, tuple[Paint, Path]] = {}
    runs: list[list[int]] = np.stack([js[keep], xs[keep], stops[keep], drawn], axis=1).tolist()
    for j, i, k, v in runs:
        paint = pal[v]
        if paint is None:
            continue
        if v not in paths:
            paths[v] = (paint, Path())
        x0, x1, y0, y1 = ox + i * c, ox + k * c, oy + j * c, oy + (j + 1) * c
        paths[v][1].M(x0, y0).H(x1).V(y1).H(x0).Z()
    for v in sorted(paths):
        paint, d = paths[v]
        s.pixel_path(d, paint, cell=c, origins=[(ox, oy)], **style)


@final
class Pixels:
    """A (rows, cols) index grid over a palette, painted with numpy, stamps, lines and
    dithering, then drawn with grid_runs. Index 0 is the background by convention.

    `grid` starts all 0; assign to it with numpy (px.grid[mask] = 2).
    """

    def __init__(self, cols: int, rows: int, palette: Sequence[Paint | None]) -> None:
        """Raises ValueError for sizes below 1 or an empty palette."""
        self.cols: Final = _count(cols, "Pixels cols", 1)
        self.rows: Final = _count(rows, "Pixels rows", 1)
        self.palette: Final = tuple(palette)
        if len(self.palette) == 0:
            raise ValueError("Pixels takes a palette of at least one entry")
        self.grid: _I = np.zeros((self.rows, self.cols), dtype=np.int64)

    def stamp(
        self,
        art: str | Sequence[str],
        x: int,
        y: int,
        key: Mapping[str, int],
        *,
        flip: bool = False,
    ) -> None:
        """Write key[ch] for every character of `art` found in `key`, the art's top-left at
        column x, row y, mirrored left to right within the art's width when `flip`; other
        characters are transparent and cells off the grid are dropped.

        Raises TypeError for a non-int position or index and IndexError for an index outside
        the palette.
        """
        rows = _rows(art, "stamp")
        ox, oy = _int(x, "stamp x"), _int(y, "stamp y")
        idx = {ch: _index(v, len(self.palette), f"stamp key {ch!r}") for ch, v in key.items()}
        width = max((len(r) for r in rows), default=0)
        for j, row in enumerate(rows):
            if not 0 <= oy + j < self.rows:
                continue
            for i, ch in enumerate(row):
                v = idx.get(ch)
                cx = ox + (width - 1 - i if flip else i)
                if v is not None and 0 <= cx < self.cols:
                    self.grid[oy + j, cx] = v

    def line(self, x0: int, y0: int, x1: int, y1: int, index: int) -> None:
        """Set the cells of the 8-connected Bresenham line from (x0, y0) to (x1, y1), both
        ends included, to `index`; cells off the grid are dropped.

        Raises TypeError for non-int arguments and IndexError for an index outside the palette.
        """
        v = _index(index, len(self.palette), "line index")
        for cx, cy in _bresenham(
            _int(x0, "line x0"), _int(y0, "line y0"), _int(x1, "line x1"), _int(y1, "line y1")
        ):
            if 0 <= cx < self.cols and 0 <= cy < self.rows:
                self.grid[cy, cx] = v

    def dither(
        self,
        field: ArrayLike,
        levels: Sequence[int],
        *,
        method: DitherMethod = "bayer",
        matrix: int = 4,
        rng: np.random.Generator | None = None,
        where: ArrayLike | None = None,
    ) -> None:
        """Quantise the (rows, cols) `field`, clamped to [0, 1], into len(levels) levels with
        dither() and write levels[q] into the grid, only where the boolean `where` is true
        when given.

        Raises ValueError for a field or mask of another shape or fewer than 2 levels,
        TypeError for a non-boolean mask, and IndexError for a level outside the palette.
        """
        f = np.asarray(field, dtype=np.float64)
        if f.shape != self.grid.shape:
            raise ValueError(
                f"Pixels.dither takes a field of shape {self.grid.shape}, got {f.shape}"
            )
        lv = np.array(
            [_index(v, len(self.palette), "Pixels.dither level") for v in levels], dtype=np.int64
        )
        vals: _I = lv[dither(f, len(lv), method=method, matrix=matrix, rng=rng)]
        if where is None:
            self.grid[:, :] = vals
            return
        m = np.asarray(where)
        if m.dtype != np.bool_:
            raise TypeError(f"Pixels.dither where takes a boolean mask, got dtype {m.dtype}")
        if m.shape != self.grid.shape:
            raise ValueError(f"Pixels.dither where takes shape {self.grid.shape}, got {m.shape}")
        self.grid[m] = vals[m]

    def draw(
        self,
        s: Canvas,
        cell: Num,
        origin: Point = (0.0, 0.0),
        *,
        skip: int | None = 0,
        **style: Unpack[Style],
    ) -> None:
        """grid_runs(s, self.grid, self.palette, cell, origin, skip=skip, **style)."""
        grid_runs(s, self.grid, self.palette, cell, origin, skip=skip, **style)


def _bresenham(x0: int, y0: int, x1: int, y1: int) -> Iterator[tuple[int, int]]:
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    err = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def bayer(n: int) -> _F:
    """The (n, n) Bayer ordered-dither threshold matrix, values (v + 0.5) / n**2.

    Raises ValueError unless n is a power of two of at least 2.
    """
    size = _count(n, "bayer n", 2)
    if size & (size - 1) != 0:
        raise ValueError(f"bayer takes a power of two, got {n!r}")
    m: _I = np.array([[0, 2], [3, 1]], dtype=np.int64)
    while len(m) < size:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / (size * size)


def blue_noise(n: int, rng: np.random.Generator, *, sigma: Num = 1.5) -> _F:
    """An (n, n) void-and-cluster blue-noise threshold mask, values (rank + 0.5) / n**2,
    drawing from `rng` exactly as v1 drew from default_rng(seed).

    Results are cached by n, sigma and the generator's state on entry; a cached call also
    leaves the generator in the state an uncached one would. Raises ValueError for n < 1 or
    a sigma not above 0, and TypeError when `rng` is not a numpy Generator.
    """
    size = _count(n, "blue_noise n", 1)
    sg = _positive(sigma, "blue_noise sigma")
    if not isinstance(rng, np.random.Generator):
        raise TypeError(f"blue_noise takes a numpy Generator from s.np_rng(key), got {rng!r}")
    key = (size, sg, pickle.dumps(rng.bit_generator.state))
    hit = _BLUE.get(key)
    if hit is None:
        hit = _BLUE[key] = (_void_and_cluster(size, rng, sg), rng.bit_generator.state)
    else:
        rng.bit_generator.state = hit[1]
    return hit[0].copy()


def _void_and_cluster(n: int, r: np.random.Generator, sigma: float) -> _F:
    """Ulichney's void-and-cluster ranking of an n x n torus, v1's steps and draws unchanged."""
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
    k = _count(size, "threshold_matrix size", 1)
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
    """Quantise the (rows, cols) `field`, clamped to [0, 1], to indices 0 .. levels - 1 of the
    same shape.

    Ordered methods threshold against threshold_matrix(method, matrix, rng): "bayer" (a
    crisp crosshatch; matrix 2, 4, 8 or 16), "clustered" (halftone dots), "bluenoise" (even
    grain), "lines" (a line screen matrix cells in pitch) and "random" (white-noise grain).
    Error diffusion: "fs", "atkinson" (drops a quarter of the error, so it is punchy),
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
    n = _count(levels, "dither levels", 2) - 1
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


def _font(font: object) -> tuple[int, int, dict[int, str]]:
    if not isinstance(font, str) or font not in FONTS:
        raise ValueError(f"font is one of {', '.join(FONTS)}, got {font!r}")
    return FONTS[font]


@functools.cache
def _bitmap(font: str, ch: str) -> NDArray[np.bool_]:
    """The cached bitmap of glyph(); callers must not modify it."""
    fw, fh, table = _font(font)
    rows = table.get(ord(ch))
    if rows is None:
        return np.zeros((fh, fw), dtype=np.bool_)
    vals = np.array([int(rows[2 * j : 2 * j + 2], 16) for j in range(fh)], dtype=np.int64)
    return ((vals[:, None] >> (fw - 1 - np.arange(fw))[None, :]) & 1).astype(np.bool_)


def glyph(ch: str, font: Font = "8x16") -> NDArray[np.bool_]:
    """The (height, width) bitmap of the character `ch` in a bundled Spleen font: "5x8" has
    ASCII and light box drawing, "8x16" adds heavy box drawing, blocks, shades, geometric
    shapes and braille. Unknown characters are blank.

    Raises ValueError for anything but one character or an unknown font.
    """
    if not isinstance(ch, str) or len(ch) != 1:
        raise ValueError(f"glyph takes one character, got {ch!r}")
    return _bitmap(font, ch).copy()


@functools.cache
def _glyph_runs(font: str, ch: str, flip: bool) -> tuple[tuple[int, int, int], ...]:
    """The (row, start, stop) runs of set pixels in a glyph, left to right per row."""
    out: list[tuple[int, int, int]] = []
    bits: list[list[bool]] = _bitmap(font, ch).tolist()
    for j, row in enumerate(bits):
        cells: list[bool] = row[::-1] if flip else row
        i = 0
        while i < len(cells):
            if not cells[i]:
                i += 1
                continue
            k = i
            while k < len(cells) and cells[k]:
                k += 1
            out.append((j, i, k))
            i = k
    return tuple(out)


def text_width(text: str, *, font: Font = "8x16", px: Num = 2, gap: int = 0) -> float:
    """The drawn width of one line of glyphs: (len(text) * (width + gap) - gap) * px, and 0 for
    an empty string.

    Raises ValueError for an unknown font, a px not above 0 or a negative gap.
    """
    fw, _, _ = _font(font)
    p = _positive(px, "text_width px")
    g = _count(gap, "text_width gap", 0)
    return 0.0 if len(text) == 0 else (len(text) * (fw + g) - g) * p


def glyphs(
    s: Canvas,
    lines: str | Sequence[str],
    paint: Paint | Callable[[int, int, str], Paint | None],
    *,
    at: Point,
    font: Font = "8x16",
    px: Num = 2,
    gap: int = 0,
    anchor: Literal["start", "middle", "end"] = "start",
    flip: bool = False,
    key: Callable[[int, int, str], Hashable] | None = None,
    **style: Unpack[Style],
) -> None:
    """Draw bitmap text as crisp pixel paths: each font pixel is px by px, and a character
    cell (width + gap) * px wide and (height + gap) * px tall. Spaces are never drawn.

    `lines` is one str split on newlines, or a sequence of lines. `paint` is one paint, or
    paint(col, row, ch) per character, None skipping it. Each line is placed on its own:
    anchor "start" puts its left edge at at[0], "middle" centres it there and "end" puts its
    right edge there; line r starts at at[1] + r * (height + gap) * px. `flip` mirrors each
    character's bitmap left to right.

    Cells group into one path per paint (by formula equality), or per key(col, row, ch)
    when given; paths come in first-seen group order, each recording the origins of the lines
    it has cells in. Raises ValueError when one group gets two paints, for an unknown font or
    anchor, a px not above 0 or a negative gap.
    """
    rows = lines.split("\n") if isinstance(lines, str) else _rows(lines, "glyphs")
    fw, fh, _ = _font(font)
    p = _positive(px, "glyphs px")
    g = _count(gap, "glyphs gap", 0)
    ax, ay = point(at, "glyphs at")
    if anchor not in ("start", "middle", "end"):
        raise ValueError(f"glyphs anchor is start, middle or end, got {anchor!r}")
    groups: dict[Hashable, tuple[Paint, Path, list[int]]] = {}
    origins: list[tuple[float, float]] = []
    for r, line in enumerate(rows):
        w = text_width(line, font=font, px=p, gap=g)
        lx = ax if anchor == "start" else ax - w / 2 if anchor == "middle" else ax - w
        ly = ay + r * (fh + g) * p
        origins.append((lx, ly))
        for c, ch in enumerate(line):
            if ch == " ":
                continue
            fill = paint(c, r, ch) if callable(paint) else paint
            if fill is None:
                continue
            group = fill if key is None else key(c, r, ch)
            entry = groups.get(group)
            if entry is None:
                entry = groups[group] = (fill, Path(), list[int]())
            elif entry[0] != fill:
                raise ValueError(f"glyphs group {group!r} got two paints: {entry[0]!r}, {fill!r}")
            d, used = entry[1], entry[2]
            ox = lx + c * (fw + g) * p
            for j, i, k in _glyph_runs(font, ch, flip):
                x0, x1, y0, y1 = ox + i * p, ox + k * p, ly + j * p, ly + (j + 1) * p
                d.M(x0, y0).H(x1).V(y1).H(x0).Z()
                if len(used) == 0 or used[-1] != r:
                    used.append(r)
    for fill, d, used in groups.values():
        if len(used) > 0:
            s.pixel_path(d, fill, cell=p, origins=[origins[r] for r in used], **style)


def sprite(
    s: Canvas,
    art: str | Sequence[str],
    palette: Mapping[str, Paint],
    cell: Num,
    origin: Point = (0.0, 0.0),
    **style: Unpack[Style],
) -> None:
    """Draw pixel art, one character per pixel: a multi-line str stripped of leading and
    trailing newlines, or a sequence of rows. `palette` maps characters to paints; others
    are transparent. Drawn through grid_runs with the palette's characters in sorted order.

    Raises ValueError for a palette key that is not one character.
    """
    rows = _rows(art, "sprite")
    keys = sorted(palette)
    for ch in keys:
        if len(ch) != 1:
            raise ValueError(f"sprite palette keys are single characters, got {ch!r}")
    idx = {ch: i + 1 for i, ch in enumerate(keys)}
    grid = np.zeros((len(rows), max((len(r) for r in rows), default=0)), dtype=np.int64)
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            grid[j, i] = idx.get(ch, 0)
    grid_runs(s, grid, [None, *(palette[ch] for ch in keys)], cell, origin, **style)

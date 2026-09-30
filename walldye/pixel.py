"""Pixel work: index grids drawn as merged runs, dithering, sprites and bitmap text.

Everything draws through Canvas.pixel_path, so each path is marked for crisp export and its
grid origin is recorded on the document.
"""

from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from typing import Final, Literal, Unpack, final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ._canvas import Canvas
from ._dither import DitherMethod, bayer, blue_noise, dither, threshold_matrix
from ._glyphs import Font, font_table, glyph, glyph_runs, text_width
from ._path import Path
from ._svg import Paint, Style
from ._vec import Num, Point, count, integer, point, positive

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

type _I = NDArray[np.int64]


def _index(v: object, size: int, what: str) -> int:
    """`v` as a palette index. Raises TypeError for a non-int and IndexError outside
    range(size)."""
    i = integer(v, what)
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
    c = positive(cell, "grid_runs cell")
    ox, oy = point(origin, "grid_runs origin")
    sk = None if skip is None else integer(skip, "grid_runs skip")
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
        self.cols: Final = count(cols, "Pixels cols", 1)
        self.rows: Final = count(rows, "Pixels rows", 1)
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
        ox, oy = integer(x, "stamp x"), integer(y, "stamp y")
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
            integer(x0, "line x0"),
            integer(y0, "line y0"),
            integer(x1, "line x1"),
            integer(y1, "line y1"),
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
        """Quantize the (rows, cols) `field`, clamped to [0, 1], into len(levels) levels with
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
    anchor "start" puts its left edge at at[0], "middle" centers it there and "end" puts its
    right edge there; line r starts at at[1] + r * (height + gap) * px. `flip` mirrors each
    character's bitmap left to right.

    Cells group into one path per paint (by formula equality), or per key(col, row, ch)
    when given; paths come in first-seen group order, each recording the origins of the lines
    it has cells in. Raises ValueError when one group gets two paints, for an unknown font or
    anchor, a px not above 0 or a negative gap.
    """
    rows = lines.split("\n") if isinstance(lines, str) else _rows(lines, "glyphs")
    fw, fh, _ = font_table(font)
    p = positive(px, "glyphs px")
    g = count(gap, "glyphs gap", 0)
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
            for j, i, k in glyph_runs(font, ch, flip):
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

"""The drawing surface a design's draw() receives, and its clip, mask and pattern sub-surfaces."""

import hashlib
import json
import random
import re
from collections.abc import Generator, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path as FsPath
from typing import Any, Final, Literal, Unpack, override

import numpy as np

from ._affine import Affine
from ._document import Builder, Line, Pending
from ._noise import Noise
from ._params import Params
from ._path import Path, fmt
from ._surfaces import Buckets, ClipSurface, Drawing, MaskSurface, PatternSurface, Sub
from ._svg import (
    FillRule,
    LineCap,
    LineJoin,
    NpRng,
    Paint,
    Ref,
    Rng,
    Stop,
    Style,
    add_linear,
    add_radial,
    attributes,
    matrix,
    path_line,
    style_values,
)
from ._vec import Num, Point, Rect, Vec, num, point

_DATA_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.(json|txt|npy)")


class Canvas[Pm: Params = Params](Drawing):
    """The surface draw() receives: canvas size, regime, params, random streams, data files
    and the drawing calls.

    It lives for one draw; any use after draw() returns raises RuntimeError("the canvas is
    closed"). While a clip, mask or pattern block is open, drawing on the canvas or opening a
    group, buckets or another such block raises RuntimeError.
    """

    def __init__(
        self, params: Pm, *, w: int, h: int, light: bool, doc: Builder, source: FsPath
    ) -> None:
        """Internal: Design.draw creates the canvas."""
        self._params: Final = params
        self._w: Final = w
        self._h: Final = h
        self._light: Final = light
        self._doc: Final = doc
        self._data: Final = source.parent / "data"
        self._open: Sub | None = None
        self._closed = False

    def _live(self) -> None:
        if self._closed:
            raise RuntimeError("the canvas is closed")

    @override
    def _target(self) -> list[Line | Pending]:
        self._live()
        if self._open is not None:
            raise RuntimeError(f"close the {self._open._name} block first")
        return self._doc.body

    @property
    def w(self) -> int:
        """The canvas width in pixels."""
        self._live()
        return self._w

    @property
    def h(self) -> int:
        """The canvas height in pixels; the short side is always 1080."""
        self._live()
        return self._h

    @property
    def landscape(self) -> bool:
        """Whether w >= h."""
        self._live()
        return self._w >= self._h

    @property
    def light(self) -> bool:
        """Whether this draw is for the light regime; the only theme fact a design reads."""
        self._live()
        return self._light

    @property
    def params(self) -> Pm:
        """The params of the version being drawn."""
        self._live()
        return self._params

    @property
    def center(self) -> Vec:
        """(w / 2, h / 2)."""
        self._live()
        return Vec(self._w / 2, self._h / 2)

    def frac(self, fx: Num, fy: Num) -> Vec:
        """The point (fx * w, fy * h)."""
        self._live()
        return Vec(num(fx, "frac") * self._w, num(fy, "frac") * self._h)

    def pick(self, *, landscape: Point, portrait: Point, snap: Num | None = None) -> Vec:
        """The `landscape` fractions on a landscape canvas, else the `portrait` ones, scaled like
        frac(); with `snap`, each coordinate rounded to a multiple of it (Python's round).

        Raises ValueError for a snap that is not above 0.
        """
        self._live()
        fx, fy = point(landscape if self._w >= self._h else portrait, "pick")
        x, y = fx * self._w, fy * self._h
        if snap is None:
            return Vec(x, y)
        k = num(snap, "pick snap")
        if k <= 0:
            raise ValueError(f"pick snap takes a number above 0, got {snap!r}")
        return Vec(float(round(x / k) * k), float(round(y / k) * k))

    def inset(self, margin: Num) -> Rect:
        """Rect(margin, margin, w - 2 margin, h - 2 margin); a negative margin grows it.

        Raises ValueError when the result has no area.
        """
        self._live()
        m = num(margin, "inset")
        r = Rect(m, m, self._w - 2 * m, self._h - 2 * m)
        if r.w <= 0 or r.h <= 0:
            raise ValueError(f"inset({margin!r}) leaves no area on a {self._w}x{self._h} canvas")
        return r

    def _stream(self, key: object) -> int | str:
        """The int key itself when no seed is set, else the derived stream name."""
        self._live()
        if isinstance(key, (bool, np.bool)):
            raise TypeError(f"stream keys are ints or strs, got {key!r}")
        k: int | str
        if isinstance(key, (int, np.integer)):
            k = int(key)
            if k < 0:
                raise ValueError(f"stream keys are ints >= 0 or strs, got {key!r}")
        elif isinstance(key, str):
            k = key
        else:
            raise TypeError(f"stream keys are ints or strs, got {key!r}")
        seed = self._params.seed
        if seed is None and isinstance(k, int):
            return k
        return f"{'' if seed is None else seed}:{k!r}"

    def rng(self, key: int | str) -> Rng:
        """A fresh random.Random for stream `key`.

        With no seed set and an int key it is random.Random(key); otherwise
        random.Random(f"{'' if seed is None else seed}:{key!r}"). Raises TypeError for a bool
        or another type and ValueError for a negative int.
        """
        return random.Random(self._stream(key))

    def np_rng(self, key: int | str) -> NpRng:
        """A fresh numpy Generator for stream `key`: np.random.default_rng(key) with no seed
        and an int key, else seeded from the first 16 bytes of sha256 of the stream name."""
        k = self._stream(key)
        if isinstance(k, str):
            k = int.from_bytes(hashlib.sha256(k.encode()).digest()[:16], "big")
        return np.random.default_rng(k)

    def noise(self, key: int | str) -> Noise:
        """A Noise for stream `key`: Noise(key) with no seed and an int key, else Noise(name)."""
        return Noise(self._stream(key))

    def data(self, name: str) -> Any:  # pyrefly: ignore[explicit-any]
        """The file wallpapers/<slug>/data/<name>, read afresh: .json parsed, .txt as text,
        .npy through np.load without pickles.

        Raises ValueError unless `name` is a plain file name (letters, digits, '.', '_', '-',
        not starting with '.', '_' or '-') ending in .json, .txt or .npy, and FileNotFoundError
        for a missing file.
        """
        self._live()
        if not isinstance(name, str) or _DATA_NAME.fullmatch(name) is None:
            raise ValueError(
                f"data names look like 'points.json', 'names.txt' or 'grid.npy', got {name!r}"
            )
        path = self._data / name
        if not path.is_file():
            raise FileNotFoundError(f"no data file {path}")
        if name.endswith(".npy"):
            return np.load(path, allow_pickle=False)
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if name.endswith(".json") else text

    def fill(
        self,
        d: Path,
        paint: Paint,
        *,
        rule: FillRule | None = None,
        opacity: Num | None = None,
    ) -> None:
        """Fill `d`: <path d fill [fill-rule] [opacity]/>. An empty path draws nothing."""
        self._target()
        self._fill(d, paint, rule, opacity)

    def stroke(
        self,
        d: Path,
        paint: Paint,
        width: Num,
        *,
        cap: LineCap | None = None,
        join: LineJoin | None = None,
        dash: Sequence[Num] | None = None,
        opacity: Num | None = None,
    ) -> None:
        """Stroke `d`: <path d fill="none" stroke stroke-width [linecap] [linejoin] [dasharray]
        [opacity]/>. An empty path draws nothing."""
        self._target()
        self._stroke(d, paint, width, cap, join, dash, opacity)

    def path(self, d: Path, *, fill: Paint, **style: Unpack[Style]) -> None:
        """Draw `d` with `fill` ("none" for an outline) and any Style keys.

        Values are checked at runtime: unknown keys and wrong types raise TypeError; NaN,
        infinity, '', negative widths, opacities outside [0, 1], bad dash lists and unknown
        literals raise ValueError; raw color strings raise TypeError. Attributes are written
        in one fixed order. An empty path draws nothing.
        """
        self._target()
        self._emit(d, {"fill": fill, **style_values(style, "path")})

    def pixel_path(
        self,
        d: Path,
        fill: Paint,
        *,
        cell: Num,
        origins: Sequence[Point],
        **style: Unpack[Style],
    ) -> None:
        """Draw pixel cells: <path d class="px" fill .../>, and when `d` is not empty record
        (cell, x, y) for each of `origins`, in order, as the document's pixel grids.

        Raises ValueError for an empty `origins` or a cell that is not above 0.
        """
        self._target()
        c = num(cell, "pixel_path cell")
        if c <= 0:
            raise ValueError(f"pixel_path cell takes a number above 0, got {cell!r}")
        grids = [(c, *point(o, "pixel_path origins")) for o in origins]
        if len(grids) == 0:
            raise ValueError("pixel_path needs at least one origin")
        self._emit(d, {"fill": fill, **style_values(style, "pixel_path")}, ' class="px"')
        if not d.empty:
            self._doc.grids.extend(grids)

    def group(self, **style: Unpack[Style]) -> AbstractContextManager[None]:
        """Wrap what is drawn inside the with block in <g ...style>...</g>.

        Children inherit what they leave unset; opacity, transform, clip_path and mask apply to
        the group as a whole.
        """
        self._target()
        return self._group(style_values(style, "group"))

    @contextmanager
    def buckets(
        self, paints: Sequence[Paint], kind: Literal["fill", "stroke"], /, **style: Unpack[Style]
    ) -> Generator[Buckets]:
        """One Path per paint, filled through b[i] and emitted when the block closes, one
        element per non-empty bucket in index order, at the position where the block opened.

        kind "fill" fills each with paints[i] plus `style`; kind "stroke" strokes each with
        paints[i], and `style` must set stroke_width (ValueError) and not stroke (TypeError).
        """
        target = self._target()
        if kind not in ("fill", "stroke"):
            raise ValueError(f"buckets kind is 'fill' or 'stroke', got {kind!r}")
        values = style_values(style, "buckets")
        if kind == "stroke":
            if "stroke" in values:
                raise TypeError("stroke buckets take their stroke from paints; drop stroke=")
            if "stroke_width" not in values:
                raise ValueError("stroke buckets need stroke_width=")
        if isinstance(paints, str) or not isinstance(paints, Sequence):
            raise TypeError(f"buckets take a sequence of paints, got {paints!r}")
        key = "fill" if kind == "fill" else "stroke"
        extra = {} if kind == "fill" else {"fill": "none"}
        attrs = [attributes({**extra, **values, key: p}, "theme") for p in paints]
        pending = Pending()
        target.append(pending)
        b = Buckets(len(attrs))
        try:
            yield b
        finally:
            b._closed = True
        for d, a in zip(b._paths, attrs, strict=True):
            if not d.empty:
                pending.lines.append(path_line(d, a))

    @contextmanager
    def clip(self) -> Generator[ClipSurface]:
        """A clip path: add geometry inside the block, then pass .ref as clip_path=."""
        self._target()
        surf = ClipSurface(Ref(self._doc.new_id("cp"), "clip"))
        with self._sub(surf):
            yield surf
        self._doc.defs += (f'<clipPath id="{surf.ref.id}">', *surf._content(), "</clipPath>")

    @contextmanager
    def mask(self) -> Generator[MaskSurface]:
        """A mask over the whole canvas: draw mask colors inside the block, then pass .ref as
        mask=."""
        self._target()
        surf = MaskSurface(Ref(self._doc.new_id("m"), "mask"), self._doc)
        with self._sub(surf):
            yield surf
        head = (
            f'<mask id="{surf.ref.id}" maskUnits="userSpaceOnUse" x="0" y="0"'
            f' width="{self._w}" height="{self._h}">'
        )
        self._doc.defs += (head, *surf._content(), "</mask>")

    @contextmanager
    def pattern(
        self, w: Num, h: Num, *, transform: Affine | None = None
    ) -> Generator[PatternSurface]:
        """A w by h tile in user space: draw inside the block in tile coordinates, then use
        .ref as a paint. Raises ValueError unless w and h are above 0."""
        self._target()
        pw, ph = num(w, "pattern w"), num(h, "pattern h")
        if pw <= 0 or ph <= 0:
            raise ValueError(f"pattern takes a size above 0, got {w!r} x {h!r}")
        tail = "" if transform is None else f' patternTransform="{matrix(transform, "transform")}"'
        surf = PatternSurface(Ref(self._doc.new_id("p"), "paint"))
        with self._sub(surf):
            yield surf
        head = (
            f'<pattern id="{surf.ref.id}" width="{fmt(pw, 3)}" height="{fmt(ph, 3)}"'
            f' patternUnits="userSpaceOnUse"{tail}>'
        )
        self._doc.defs += (head, *surf._content(), "</pattern>")

    @contextmanager
    def _sub(self, surf: Sub) -> Generator[None]:
        self._open = surf
        try:
            yield
        finally:
            self._open = None
            surf._closed = True

    def linear_gradient(
        self,
        stops: Sequence[Stop],
        p0: Point,
        p1: Point,
        *,
        units: Literal["user", "bbox"] = "user",
    ) -> Ref:
        """A linear gradient paint from p0 to p1, appended to <defs> at once.

        units "user" (canvas pixels) writes gradientUnits="userSpaceOnUse"; "bbox" uses the
        painted shape's box (0 to 1). Raises ValueError without stops, for offsets outside
        [0, 1] or decreasing, and for stop opacity outside [0, 1].
        """
        self._live()
        return add_linear(self._doc, "theme", stops, p0, p1, units)

    def radial_gradient(
        self,
        stops: Sequence[Stop],
        center: Point,
        r: Num,
        *,
        focus: Point | None = None,
        units: Literal["user", "bbox"] = "user",
    ) -> Ref:
        """A radial gradient paint around `center` with radius `r` and an optional focus;
        otherwise as linear_gradient."""
        self._live()
        return add_radial(self._doc, "theme", stops, center, r, focus, units)


def close(canvas: Canvas) -> None:
    """End `canvas`'s draw; every later use of it raises RuntimeError."""
    canvas._closed = True

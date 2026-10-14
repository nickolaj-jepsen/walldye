"""The drawing surface a design's draw() receives, its clip, mask and pattern sub-surfaces,
and its motif block."""

import hashlib
import json
import random
import re
from collections.abc import Generator, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path as FsPath
from typing import Any, Final, Literal, Unpack, final, override

import numpy as np

from ._affine import Affine
from ._document import Box, Builder, Line, MotifInfo, Pending
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
SCALE: Final = (0.5, 2.0)  # the widest range of sizes a motif may offer a visitor


@final
class Motif:
    """The inside of a `with s.motif(...) as m:` block, drawn in motif-local units around the
    anchor."""

    def __init__(self, cover: Rect) -> None:
        """Internal: Canvas.motif makes these."""
        self.cover: Final = cover
        """The motif-local area that any allowed placement can show: what surroundings drawn
        inside the motif fill so that the screen stays covered wherever it goes."""


def _box(value: object, what: str) -> Box:
    """A radius (a box centered on the origin) or a Rect, as (x, y, w, h). Raises TypeError
    for anything else and ValueError for a size that is not above 0."""
    if isinstance(value, Rect):
        x, y, w, h = (num(v, what) for v in value)
    else:
        r = num(value, what)
        x, y, w, h = -r, -r, 2 * r, 2 * r
    if w <= 0 or h <= 0:
        raise ValueError(f"{what} takes a radius or a Rect with a size above 0, got {value!r}")
    return x, y, w, h


class Canvas[Pm: Params = Params](Drawing):
    """The surface draw() receives: canvas size, regime, params, random streams, data files
    and the drawing calls.

    It lives for one draw; any use after draw() returns raises RuntimeError("the canvas is
    closed"). While a clip, mask or pattern block is open, drawing on the canvas or opening a
    group, buckets or another such block raises RuntimeError. Inside a motif block, the canvas
    size and positions (w, h, center, frac, pick, inset) and mask() raise RuntimeError, and
    once it closes nothing more may be drawn.
    """

    def __init__(
        self,
        params: Pm,
        *,
        w: int,
        h: int,
        light: bool,
        doc: Builder,
        source: FsPath,
        shift: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        """Internal: Design.draw creates the canvas. `shift` (dx, dy) is added to every
        position center, frac and pick return, and lets the motif's anchor leave the canvas."""
        self._params: Final = params
        self._w: Final = w
        self._h: Final = h
        self._light: Final = light
        self._doc: Final = doc
        self._data: Final = source.parent / "data"
        self._shift: Final = shift
        self._open: Sub | None = None
        self._closed = False
        self._depth = 0  # groups open around what is drawn now
        self._buckets = 0  # buckets blocks open, whose paths land where each opened
        self._motif: Literal["before", "open", "after"] = "before"
        self._anchor = (0.0, 0.0)  # the open motif's, where its local units start

    def _live(self) -> None:
        if self._closed:
            raise RuntimeError("the canvas is closed")

    def _layout(self, what: str) -> None:
        self._live()
        if self._motif == "open":
            raise RuntimeError(
                f"s.{what} is not available inside the motif, which may not depend on the"
                " canvas or its place on it; size its surroundings from m.cover"
            )

    @override
    def _target(self) -> list[Line | Pending]:
        self._live()
        if self._open is not None:
            raise RuntimeError(f"close the {self._open._name} block first")
        if self._motif == "after":
            raise RuntimeError("the motif is the last thing drawn; draw the rest before it")
        return self._doc.body

    @property
    def w(self) -> int:
        """The canvas width in pixels."""
        self._layout("w")
        return self._w

    @property
    def h(self) -> int:
        """The canvas height in pixels; the short side is always 1080."""
        self._layout("h")
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
        self._layout("center")
        return Vec(self._w / 2 + self._shift[0], self._h / 2 + self._shift[1])

    def frac(self, fx: Num, fy: Num) -> Vec:
        """The point (fx * w, fy * h)."""
        self._layout("frac")
        x, y = num(fx, "frac") * self._w, num(fy, "frac") * self._h
        return Vec(x + self._shift[0], y + self._shift[1])

    def pick(self, *, landscape: Point, portrait: Point, snap: Num | None = None) -> Vec:
        """The `landscape` fractions on a landscape canvas, else the `portrait` ones, scaled like
        frac(); with `snap`, each coordinate rounded to a multiple of it (Python's round).

        Raises ValueError for a snap that is not above 0.
        """
        self._layout("pick")
        fx, fy = point(landscape if self._w >= self._h else portrait, "pick")
        x, y = fx * self._w + self._shift[0], fy * self._h + self._shift[1]
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
        self._layout("inset")
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
        (cell, x, y) for each of `origins`, in order, as the document's pixel grids, in canvas
        units (inside the motif, moved by its anchor).

        Raises ValueError for an empty `origins` or a cell that is not above 0.
        """
        self._target()
        c = num(cell, "pixel_path cell")
        if c <= 0:
            raise ValueError(f"pixel_path cell takes a number above 0, got {cell!r}")
        ax, ay = self._anchor
        grids = [(c, x + ax, y + ay) for x, y in (point(o, "pixel_path origins") for o in origins)]
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
        return self._nested(style_values(style, "group"))

    @contextmanager
    def _nested(self, values: dict[str, object]) -> Generator[None]:
        self._depth += 1
        try:
            with self._group(values):
                yield
        finally:
            self._depth -= 1

    @contextmanager
    def motif(
        self,
        at: Point,
        extent: Num | Rect | Literal["cover"],
        *,
        handle: Num | Rect | None = None,
        cell: Num | None = None,
        scale: tuple[Num, Num] = SCALE,
    ) -> Generator[Motif]:
        """The one thing on the canvas a visitor may move and resize: what is drawn inside the
        block goes into <g data-motif="" transform="translate(at)">, in motif-local units around
        `at`, and the site rewrites that transform to place it.

        `extent` bounds every mark drawn inside: a radius, a Rect, or "cover" for a motif that
        fills m.cover with its surroundings (an overscan motif), which then needs `handle`.
        `handle`, a radius or Rect defaulting to the extent, is what a visitor grabs to move
        it. `cell` is the motif's pixel cell, so sizes keep it a whole number of units.
        `scale` is the range of sizes offered, (lo, hi) with SCALE[0] <= lo <= 1 <= hi <=
        SCALE[1]. The anchor may go anywhere on the canvas.

        Raises RuntimeError for a second motif, a motif inside a group, buckets or another block, or
        any drawing after it closes; ValueError for an `at` off the canvas, a size that is not
        above 0, a cell that is not a whole number of units, a scale outside those bounds, or "cover" without
        a handle; TypeError for an extent or handle of another type.
        """
        target = self._target()
        if self._motif != "before":
            raise RuntimeError("a design has one motif at most")
        if self._depth > 0:
            raise RuntimeError("open the motif on the canvas itself, outside any group")
        if self._buckets > 0:
            raise RuntimeError("close the buckets block before opening the motif")
        x, y = point(at, "motif at")
        # A shifted draw only compares what the motif holds, so its anchor may leave the canvas.
        if self._shift == (0.0, 0.0) and not (0 <= x <= self._w and 0 <= y <= self._h):
            raise ValueError(f"the motif's anchor ({x:g}, {y:g}) is off the canvas")
        lo, hi = (num(v, "motif scale") for v in scale)
        if not SCALE[0] <= lo <= 1 <= hi <= SCALE[1]:
            raise ValueError(
                f"motif scale is (lo, hi) with {SCALE[0]:g} <= lo <= 1 <= hi <= {SCALE[1]:g},"
                f" got {scale!r}"
            )
        cover = Rect(-self._w / lo, -self._h / lo, 2 * self._w / lo, 2 * self._h / lo)
        overscan = isinstance(extent, str)
        if overscan and extent != "cover":
            raise ValueError(f'motif extent is a radius, a Rect or "cover", got {extent!r}')
        if overscan and handle is None:
            raise ValueError('a motif with extent="cover" needs handle=')
        box = tuple(cover) if overscan else _box(extent, "motif extent")
        grab = box if handle is None else _box(handle, "motif handle")
        k = None if cell is None else num(cell, "motif cell")
        # A whole cell keeps size 1 whole and gives every scale at least that one size.
        if k is not None and (k < 1 or k != int(k)):
            raise ValueError(f"motif cell takes a whole number of units, got {cell!r}")
        target.append([f'<g data-motif="" transform="translate({fmt(x, 2)} {fmt(y, 2)})">'])
        self._motif = "open"
        self._anchor = (x, y)
        try:
            yield Motif(cover)
        finally:
            self._motif = "after"
            self._anchor = (0.0, 0.0)
        self._doc.body.append(["</g>"])
        self._doc.motif = MotifInfo((x, y), tuple(cover), box, grab, overscan, k, (lo, hi))

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
        self._buckets += 1
        try:
            yield b
        finally:
            b._closed = True
            self._buckets -= 1
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
        mask=. Not inside a motif, whose units are not the canvas's."""
        self._target()
        if self._motif == "open":
            raise RuntimeError("a mask covers the canvas, so draw it outside the motif")
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

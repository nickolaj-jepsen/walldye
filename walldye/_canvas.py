"""The drawing surface a design's draw() receives, and its clip, mask and pattern sub-surfaces."""

import hashlib
import json
import operator
import random
import re
from collections.abc import Generator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path as FsPath
from typing import Any, Final, Literal, SupportsIndex, TypedDict, Unpack, final, override

import numpy as np

from ._affine import Affine
from ._color import Color, MaskColor
from ._document import Builder, Fragment, Line, Pending
from ._noise import Noise
from ._params import Params
from ._path import Path, fmt
from ._vec import Num, Point, Rect, Vec, num, point

type LineCap = Literal["butt", "round", "square"]
type LineJoin = Literal["miter", "round", "bevel"]
type FillRule = Literal["nonzero", "evenodd"]
type Rng = random.Random
type NpRng = np.random.Generator


@final
@dataclass(frozen=True, slots=True)
class Ref:
    """A reference to a gradient, pattern, clip or mask; str() is "url(#id)".

    Only the drawing API makes these. `kind` says where it is accepted: "paint" in a canvas or
    pattern paint position, "mask_paint" in a mask paint position, "clip" as clip_path= and
    "mask" as mask=.
    """

    id: str
    kind: Literal["paint", "mask_paint", "clip", "mask"]

    def __str__(self) -> str:
        return f"url(#{self.id})"


type Paint = Color | Literal["none"] | Ref
type MaskPaint = MaskColor | Literal["none"] | Ref
type Stop = tuple[Num, Color] | tuple[Num, Color, Num]
type MaskStop = tuple[Num, MaskColor] | tuple[Num, MaskColor, Num]


class Style(TypedDict, total=False):
    """Presentation attributes shared by drawing calls; see Canvas.path for the rules."""

    stroke: Paint
    stroke_width: Num
    stroke_linecap: LineCap
    stroke_linejoin: LineJoin
    stroke_dasharray: Sequence[Num]
    stroke_dashoffset: Num
    stroke_opacity: Num
    fill_opacity: Num
    fill_rule: FillRule
    opacity: Num
    transform: Affine
    clip_path: Ref
    mask: Ref


# Every attribute the API writes, in the one order it writes them: (style key, SVG name).
_ORDER: Final = (
    ("fill", "fill"),
    ("fill_rule", "fill-rule"),
    ("fill_opacity", "fill-opacity"),
    ("stroke", "stroke"),
    ("stroke_width", "stroke-width"),
    ("stroke_linecap", "stroke-linecap"),
    ("stroke_linejoin", "stroke-linejoin"),
    ("stroke_dasharray", "stroke-dasharray"),
    ("stroke_dashoffset", "stroke-dashoffset"),
    ("stroke_opacity", "stroke-opacity"),
    ("opacity", "opacity"),
    ("transform", "transform"),
    ("clip_path", "clip-path"),
    ("mask", "mask"),
)
_KEYS: Final = frozenset(k for k, _ in _ORDER)
_STYLE_KEYS: Final = _KEYS - {"fill"}
_LITERALS: Final[dict[str, tuple[str, ...]]] = {
    "fill_rule": ("nonzero", "evenodd"),
    "stroke_linecap": ("butt", "round", "square"),
    "stroke_linejoin": ("miter", "round", "bevel"),
}
_UNIT: Final = frozenset({"opacity", "fill_opacity", "stroke_opacity"})
_DATA_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.(json|txt|npy)")

type _Mode = Literal["theme", "mask"]


def _number(v: object, what: str) -> str:
    if isinstance(v, str):
        if v == "":
            raise ValueError(f"{what} takes a number, got ''")
        raise TypeError(f"{what} takes a number, got {v!r}")
    return fmt(v, 2, what)


def _paint(v: object, what: str, mode: _Mode) -> list[Fragment]:
    """The fragments of one paint value, checked for `mode` ("theme" or "mask")."""
    if isinstance(v, Color):
        if mode == "theme":
            return [v]
        raise TypeError(f"{what}: a mask takes mask colors (MASK_WHITE, MASK_BLACK), got {v!r}")
    if isinstance(v, MaskColor):
        if mode == "mask":
            return [v]
        raise TypeError(f"{what}: mask colors only paint inside a mask block, got {v!r}")
    if isinstance(v, Ref):
        want = "paint" if mode == "theme" else "mask_paint"
        if v.kind != want:
            raise TypeError(f"{what} takes a {want} reference, got a {v.kind} reference")
        return [str(v)]
    if isinstance(v, str):
        if v == "none":
            return ["none"]
        raise TypeError("raw color strings are not paints; use a token or mix()")
    raise TypeError(f"{what} takes a color, 'none' or a reference, got {v!r}")


def _matrix(t: object, what: str) -> str:
    if not isinstance(t, Affine):
        raise TypeError(f"{what} takes an Affine, got {t!r}")
    abcd = " ".join(fmt(v, 6) for v in (t.a, t.b, t.c, t.d))
    return f"matrix({abcd} {fmt(t.e, 2)} {fmt(t.f, 2)})"


def _value(key: str, v: object, mode: _Mode) -> list[Fragment]:
    """The attribute value fragments of Style key `key`.

    Raises TypeError for a value of the wrong type, and ValueError for an unknown literal, an
    empty, negative or all-zero dash, a negative width or an opacity outside [0, 1].
    """
    if key in ("fill", "stroke"):
        return _paint(v, key, mode)
    if key in _LITERALS:
        if not isinstance(v, str) or v not in _LITERALS[key]:
            raise ValueError(f"{key} takes one of {', '.join(_LITERALS[key])}, got {v!r}")
        return [v]
    if key == "stroke_dasharray":
        if isinstance(v, (str, bytes)) or not isinstance(v, (Sequence, np.ndarray)):
            raise TypeError(f"{key} takes a sequence of numbers, got {v!r}")
        seq: Sequence[object] | np.ndarray[tuple[int, ...], np.dtype[np.generic]] = v
        texts = [_number(x, key) for x in seq]
        values = [num(x, key) for x in seq]
        if len(values) == 0 or any(x < 0 for x in values) or all(x == 0 for x in values):
            raise ValueError(f"{key} takes numbers >= 0, not all 0, got {v!r}")
        return [" ".join(texts)]
    if key == "transform":
        return [_matrix(v, key)]
    if key in ("clip_path", "mask"):
        want = "clip" if key == "clip_path" else "mask"
        if not isinstance(v, Ref) or v.kind != want:
            raise TypeError(f"{key} takes a {want} reference, got {v!r}")
        return [str(v)]
    text = _number(v, key)
    f = num(v, key)
    if key == "stroke_width" and f < 0:
        raise ValueError(f"{key} takes a number >= 0, got {v!r}")
    if key in _UNIT and not 0 <= f <= 1:
        raise ValueError(f"{key} takes a number within [0, 1], got {v!r}")
    return [text]


def _attrs(values: Mapping[str, object], mode: _Mode) -> list[Fragment]:
    """` name="value"` fragments for `values` in the fixed attribute order.

    Raises TypeError for a key outside the order.
    """
    unknown = values.keys() - _KEYS
    if len(unknown) > 0:
        raise TypeError(f"unknown style keys: {', '.join(sorted(unknown))}")
    out: list[Fragment] = []
    for key, name in _ORDER:
        if key in values:
            out += (f' {name}="', *_value(key, values[key], mode), '"')
    return out


def _style(style: Mapping[str, object], what: str) -> dict[str, object]:
    unknown = style.keys() - _STYLE_KEYS
    if len(unknown) > 0:
        raise TypeError(f"{what} got unknown style keys: {', '.join(sorted(unknown))}")
    return dict(style)


def _path_line(d: Path, attrs: list[Fragment], cls: str = "") -> Line:
    if not isinstance(d, Path):
        raise TypeError(f"drawing calls take a Path from P(), got {d!r}")
    return [f'<path d="{d}"{cls}', *attrs, "/>"]


def _optional(**kw: object) -> dict[str, object]:
    return {k: v for k, v in kw.items() if v is not None}


class _Drawing:
    """Emitting paths and groups onto a list of lines, for the canvas, mask and pattern
    surfaces."""

    _mode: _Mode = "theme"

    def _target(self) -> list[Line | Pending]:
        raise NotImplementedError

    def _emit(self, d: Path, values: dict[str, object], cls: str = "") -> None:
        attrs = _attrs(values, self._mode)
        line = _path_line(d, attrs, cls)
        if not d.empty:
            self._target().append(line)

    def _fill(self, d: Path, paint: object, rule: object, opacity: object) -> None:
        self._emit(d, {"fill": paint, **_optional(fill_rule=rule, opacity=opacity)})

    def _stroke(
        self,
        d: Path,
        paint: object,
        width: object,
        cap: object,
        join: object,
        dash: object,
        opacity: object,
    ) -> None:
        values = {"fill": "none", "stroke": paint, "stroke_width": width}
        values |= _optional(
            stroke_linecap=cap, stroke_linejoin=join, stroke_dasharray=dash, opacity=opacity
        )
        self._emit(d, values)

    @contextmanager
    def _group(self, values: dict[str, object]) -> Generator[None]:
        attrs = _attrs(values, self._mode)
        target = self._target()
        target.append(["<g", *attrs, ">"])
        yield
        self._target().append(["</g>"])


@final
class Buckets:
    """One Path per paint of a buckets block, filled through b[i]."""

    def __init__(self, n: int) -> None:
        self._paths: Final = [Path() for _ in range(n)]
        self._closed = False

    def __getitem__(self, i: SupportsIndex) -> Path:
        """The path for paints[i]. Raises IndexError outside range(len(paints)) and
        RuntimeError once the block has closed."""
        if self._closed:
            raise RuntimeError("the buckets block is closed")
        if isinstance(i, (bool, np.bool)):
            raise TypeError(f"buckets take an int index, got {i!r}")
        k = operator.index(i)
        if not 0 <= k < len(self._paths):
            raise IndexError(f"bucket {k} is outside 0..{len(self._paths) - 1}")
        return self._paths[k]

    def __len__(self) -> int:
        """The number of paints. Raises RuntimeError once the block has closed."""
        if self._closed:
            raise RuntimeError("the buckets block is closed")
        return len(self._paths)


class _Sub:
    """What the three sub-surfaces share: an id, a ref and the open/closed state."""

    _name: str

    def __init__(self, ref: Ref) -> None:
        self.ref: Final = ref
        self._lines: list[Line | Pending] = []
        self._closed = False

    def _live(self) -> None:
        if self._closed:
            raise RuntimeError(f"the {self._name} block is closed")

    def _content(self) -> list[Fragment]:
        out: list[Fragment] = []
        for item in self._lines:
            for line in item.lines if isinstance(item, Pending) else (item,):
                out += line
        return out


@final
class ClipSurface(_Sub):
    """The inside of a `with s.clip() as c:` block: geometry only; use c.ref as clip_path=."""

    _name = "clip"

    def add(self, d: Path, *, rule: FillRule = "nonzero", transform: Affine | None = None) -> None:
        """Add `d` to the clip region, with its own clip rule and transform."""
        self._live()
        if rule not in ("nonzero", "evenodd"):
            raise ValueError(f"rule takes nonzero or evenodd, got {rule!r}")
        attrs = ' clip-rule="evenodd"' if rule == "evenodd" else ""
        if transform is not None:
            attrs += f' transform="{_matrix(transform, "transform")}"'
        line = _path_line(d, [attrs])
        if not d.empty:
            self._lines.append(line)


@final
class MaskSurface(_Sub, _Drawing):
    """The inside of a `with s.mask() as m:` block: mask colors only (MASK_WHITE shows,
    MASK_BLACK hides); use m.ref as mask=."""

    _name = "mask"
    _mode: _Mode = "mask"

    def __init__(self, ref: Ref, doc: Builder) -> None:
        super().__init__(ref)
        self._doc: Final = doc

    @override
    def _target(self) -> list[Line | Pending]:
        self._live()
        return self._lines

    def fill(
        self,
        d: Path,
        paint: MaskPaint,
        *,
        rule: FillRule | None = None,
        opacity: Num | None = None,
    ) -> None:
        """Fill `d` with a mask paint; see Canvas.fill."""
        self._live()
        self._fill(d, paint, rule, opacity)

    def stroke(
        self,
        d: Path,
        paint: MaskPaint,
        width: Num,
        *,
        cap: LineCap | None = None,
        join: LineJoin | None = None,
        dash: Sequence[Num] | None = None,
        opacity: Num | None = None,
    ) -> None:
        """Stroke `d` with a mask paint; see Canvas.stroke."""
        self._live()
        self._stroke(d, paint, width, cap, join, dash, opacity)

    def group(
        self, *, opacity: Num | None = None, transform: Affine | None = None
    ) -> AbstractContextManager[None]:
        """Wrap what is drawn inside in <g> with the given opacity and transform."""
        self._live()
        return self._group(_optional(opacity=opacity, transform=transform))

    def linear_gradient(
        self,
        stops: Sequence[MaskStop],
        p0: Point,
        p1: Point,
        *,
        units: Literal["user", "bbox"] = "user",
    ) -> Ref:
        """A linear gradient of mask colors for this mask's content; see Canvas."""
        self._live()
        return _linear(self._doc, "mask", stops, p0, p1, units)

    def radial_gradient(
        self,
        stops: Sequence[MaskStop],
        center: Point,
        r: Num,
        *,
        focus: Point | None = None,
        units: Literal["user", "bbox"] = "user",
    ) -> Ref:
        """A radial gradient of mask colors for this mask's content; see Canvas."""
        self._live()
        return _radial(self._doc, "mask", stops, center, r, focus, units)


@final
class PatternSurface(_Sub, _Drawing):
    """The inside of a `with s.pattern(w, h) as pat:` block, in pattern-local coordinates
    (0..w, 0..h) with theme paints; use pat.ref as a paint."""

    _name = "pattern"

    @override
    def _target(self) -> list[Line | Pending]:
        self._live()
        return self._lines

    def fill(
        self,
        d: Path,
        paint: Paint,
        *,
        rule: FillRule | None = None,
        opacity: Num | None = None,
    ) -> None:
        """Fill `d`; see Canvas.fill."""
        self._live()
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
        """Stroke `d`; see Canvas.stroke."""
        self._live()
        self._stroke(d, paint, width, cap, join, dash, opacity)

    def path(self, d: Path, *, fill: Paint, **style: Unpack[Style]) -> None:
        """Draw `d` with any Style; see Canvas.path."""
        self._live()
        self._emit(d, {"fill": fill, **_style(style, "path")})

    def group(self, **style: Unpack[Style]) -> AbstractContextManager[None]:
        """Wrap what is drawn inside in <g> with `style`; see Canvas.group."""
        self._live()
        return self._group(_style(style, "group"))


def _stops(stops: object, mode: _Mode, what: str) -> list[Fragment]:
    """The <stop/> fragments of a gradient.

    Raises ValueError for no stops, offsets outside [0, 1] or decreasing, or an opacity outside
    [0, 1], and TypeError for a malformed stop or a stop without a color.
    """
    if isinstance(stops, str) or not isinstance(stops, Sequence) or len(stops) == 0:
        raise ValueError(f"{what} takes at least one stop (offset, color[, opacity])")
    seq: Sequence[object] = stops
    out: list[Fragment] = []
    last = 0.0
    for stop in seq:
        if not isinstance(stop, tuple) or len(stop) not in (2, 3):
            raise TypeError(f"{what} stops are (offset, color[, opacity]), got {stop!r}")
        parts: tuple[object, ...] = stop
        off = num(parts[0], f"{what} offset")
        if not last <= off <= 1:
            raise ValueError(f"{what} offsets are within [0, 1] and non-decreasing, got {off}")
        last = off
        color = parts[1]
        if not isinstance(color, (Color, MaskColor)):
            raise TypeError(f"{what} stops take colors, got {color!r}")
        frags = [f'<stop offset="{fmt(off, 3)}" stop-color="', *_paint(color, what, mode), '"']
        if len(parts) == 3:
            a = num(parts[2], f"{what} stop opacity")
            if not 0 <= a <= 1:
                raise ValueError(f"{what} stop opacity is within [0, 1], got {a}")
            frags.append(f' stop-opacity="{fmt(a, 3)}"')
        out += (*frags, "/>")
    return out


def _units(units: object, what: str) -> str:
    if units == "user":
        return ' gradientUnits="userSpaceOnUse"'
    if units == "bbox":
        return ""
    raise ValueError(f"{what} units are 'user' or 'bbox', got {units!r}")


def _linear(doc: Builder, mode: _Mode, stops: object, p0: Point, p1: Point, units: object) -> Ref:
    x1, y1 = point(p0, "linear_gradient p0")
    x2, y2 = point(p1, "linear_gradient p1")
    body = _stops(stops, mode, "linear_gradient")
    tail = _units(units, "linear_gradient")
    ref = Ref(doc.new_id("lg"), "paint" if mode == "theme" else "mask_paint")
    xy = f'x1="{fmt(x1, 3)}" y1="{fmt(y1, 3)}" x2="{fmt(x2, 3)}" y2="{fmt(y2, 3)}"'
    doc.defs += (f'<linearGradient id="{ref.id}" {xy}{tail}>', *body, "</linearGradient>")
    return ref


def _radial(
    doc: Builder,
    mode: _Mode,
    stops: object,
    center: Point,
    r: Num,
    focus: Point | None,
    units: object,
) -> Ref:
    cx, cy = point(center, "radial_gradient center")
    rr = num(r, "radial_gradient r")
    if rr < 0:
        raise ValueError(f"radial_gradient takes r >= 0, got {r!r}")
    head = f'cx="{fmt(cx, 3)}" cy="{fmt(cy, 3)}" r="{fmt(rr, 3)}"'
    if focus is not None:
        fx, fy = point(focus, "radial_gradient focus")
        head += f' fx="{fmt(fx, 3)}" fy="{fmt(fy, 3)}"'
    body = _stops(stops, mode, "radial_gradient")
    tail = _units(units, "radial_gradient")
    ref = Ref(doc.new_id("rg"), "paint" if mode == "theme" else "mask_paint")
    doc.defs += (f'<radialGradient id="{ref.id}" {head}{tail}>', *body, "</radialGradient>")
    return ref


class Canvas[Pm: Params = Params](_Drawing):
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
        self._open: _Sub | None = None
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

    def _close(self) -> None:
        """End the draw; every later use raises RuntimeError."""
        self._closed = True

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
        self._emit(d, {"fill": fill, **_style(style, "path")})

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
        self._emit(d, {"fill": fill, **_style(style, "pixel_path")}, ' class="px"')
        if not d.empty:
            self._doc.grids.extend(grids)

    def group(self, **style: Unpack[Style]) -> AbstractContextManager[None]:
        """Wrap what is drawn inside the with block in <g ...style>...</g>.

        Children inherit what they leave unset; opacity, transform, clip_path and mask apply to
        the group as a whole.
        """
        self._target()
        return self._group(_style(style, "group"))

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
        values = _style(style, "buckets")
        if kind == "stroke":
            if "stroke" in values:
                raise TypeError("stroke buckets take their stroke from paints; drop stroke=")
            if "stroke_width" not in values:
                raise ValueError("stroke buckets need stroke_width=")
        if isinstance(paints, str) or not isinstance(paints, Sequence):
            raise TypeError(f"buckets take a sequence of paints, got {paints!r}")
        key = "fill" if kind == "fill" else "stroke"
        extra = {} if kind == "fill" else {"fill": "none"}
        attrs = [_attrs({**extra, **values, key: p}, "theme") for p in paints]
        pending = Pending()
        target.append(pending)
        b = Buckets(len(attrs))
        try:
            yield b
        finally:
            b._closed = True
        for d, a in zip(b._paths, attrs, strict=True):
            if not d.empty:
                pending.lines.append(_path_line(d, a))

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
        tail = "" if transform is None else f' patternTransform="{_matrix(transform, "transform")}"'
        surf = PatternSurface(Ref(self._doc.new_id("p"), "paint"))
        with self._sub(surf):
            yield surf
        head = (
            f'<pattern id="{surf.ref.id}" width="{fmt(pw, 3)}" height="{fmt(ph, 3)}"'
            f' patternUnits="userSpaceOnUse"{tail}>'
        )
        self._doc.defs += (head, *surf._content(), "</pattern>")

    @contextmanager
    def _sub(self, surf: _Sub) -> Generator[None]:
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
        return _linear(self._doc, "theme", stops, p0, p1, units)

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
        return _radial(self._doc, "theme", stops, center, r, focus, units)

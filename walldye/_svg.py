"""The SVG the drawing API writes: paints, references, presentation attributes in their one
order, and gradients, each value checked before it is written."""

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, TypedDict, final

import numpy as np

from ._affine import Affine
from ._color import Color, MaskColor
from ._document import Builder, Fragment, Line
from ._path import Path, fmt
from ._vec import Num, Point, num, point

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

type Mode = Literal["theme", "mask"]


def _number(v: object, what: str) -> str:
    if isinstance(v, str):
        if v == "":
            raise ValueError(f"{what} takes a number, got ''")
        raise TypeError(f"{what} takes a number, got {v!r}")
    return fmt(v, 2, what)


def _paint(v: object, what: str, mode: Mode) -> list[Fragment]:
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


def matrix(t: object, what: str) -> str:
    if not isinstance(t, Affine):
        raise TypeError(f"{what} takes an Affine, got {t!r}")
    abcd = " ".join(fmt(v, 6) for v in (t.a, t.b, t.c, t.d))
    return f"matrix({abcd} {fmt(t.e, 2)} {fmt(t.f, 2)})"


def _value(key: str, v: object, mode: Mode) -> list[Fragment]:
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
        return [matrix(v, key)]
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


def attributes(values: Mapping[str, object], mode: Mode) -> list[Fragment]:
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


def style_values(style: Mapping[str, object], what: str) -> dict[str, object]:
    unknown = style.keys() - _STYLE_KEYS
    if len(unknown) > 0:
        raise TypeError(f"{what} got unknown style keys: {', '.join(sorted(unknown))}")
    return dict(style)


def path_line(d: Path, attrs: list[Fragment], cls: str = "") -> Line:
    if not isinstance(d, Path):
        raise TypeError(f"drawing calls take a Path from P(), got {d!r}")
    return [f'<path d="{d}"{cls}', *attrs, "/>"]


def optional(**kw: object) -> dict[str, object]:
    return {k: v for k, v in kw.items() if v is not None}


def _stops(stops: object, mode: Mode, what: str) -> list[Fragment]:
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


def add_linear(doc: Builder, mode: Mode, stops: object, p0: Point, p1: Point, units: object) -> Ref:
    x1, y1 = point(p0, "linear_gradient p0")
    x2, y2 = point(p1, "linear_gradient p1")
    body = _stops(stops, mode, "linear_gradient")
    tail = _units(units, "linear_gradient")
    ref = Ref(doc.new_id("lg"), "paint" if mode == "theme" else "mask_paint")
    xy = f'x1="{fmt(x1, 3)}" y1="{fmt(y1, 3)}" x2="{fmt(x2, 3)}" y2="{fmt(y2, 3)}"'
    doc.defs += (f'<linearGradient id="{ref.id}" {xy}{tail}>', *body, "</linearGradient>")
    return ref


def add_radial(
    doc: Builder,
    mode: Mode,
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

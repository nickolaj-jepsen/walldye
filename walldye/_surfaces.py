"""Emitting paths and groups, shared by the canvas and the clip, mask and pattern
sub-surfaces its blocks open."""

import operator
from collections.abc import Generator, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import Final, Literal, SupportsIndex, Unpack, final, override

import numpy as np

from ._affine import Affine
from ._document import Builder, Fragment, Line, Pending
from ._path import Path
from ._svg import (
    FillRule,
    LineCap,
    LineJoin,
    MaskPaint,
    MaskStop,
    Mode,
    Paint,
    Ref,
    Style,
    add_linear,
    add_radial,
    attributes,
    matrix,
    optional,
    path_line,
    style_values,
)
from ._vec import Num, Point


class Drawing:
    """Emitting paths and groups onto a list of lines, for the canvas, mask and pattern
    surfaces."""

    _mode: Mode = "theme"

    def _target(self) -> list[Line | Pending]:
        raise NotImplementedError

    def _emit(self, d: Path, values: dict[str, object], cls: str = "") -> None:
        attrs = attributes(values, self._mode)
        line = path_line(d, attrs, cls)
        if not d.empty:
            self._target().append(line)

    def _fill(self, d: Path, paint: object, rule: object, opacity: object) -> None:
        self._emit(d, {"fill": paint, **optional(fill_rule=rule, opacity=opacity)})

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
        values |= optional(
            stroke_linecap=cap, stroke_linejoin=join, stroke_dasharray=dash, opacity=opacity
        )
        self._emit(d, values)

    @contextmanager
    def _group(self, values: dict[str, object]) -> Generator[None]:
        attrs = attributes(values, self._mode)
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


class Sub:
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
class ClipSurface(Sub):
    """The inside of a `with s.clip() as c:` block: geometry only; use c.ref as clip_path=."""

    _name = "clip"

    def add(self, d: Path, *, rule: FillRule = "nonzero", transform: Affine | None = None) -> None:
        """Add `d` to the clip region, with its own clip rule and transform."""
        self._live()
        if rule not in ("nonzero", "evenodd"):
            raise ValueError(f"rule takes nonzero or evenodd, got {rule!r}")
        attrs = ' clip-rule="evenodd"' if rule == "evenodd" else ""
        if transform is not None:
            attrs += f' transform="{matrix(transform, "transform")}"'
        line = path_line(d, [attrs])
        if not d.empty:
            self._lines.append(line)


class PaintSurface[P](Sub, Drawing):
    """A sub-surface that fills and strokes with paints of type `P`."""

    @override
    def _target(self) -> list[Line | Pending]:
        self._live()
        return self._lines

    def fill(
        self,
        d: Path,
        paint: P,
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
        paint: P,
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


@final
class MaskSurface(PaintSurface[MaskPaint]):
    """The inside of a `with s.mask() as m:` block: mask colors only (MASK_WHITE shows,
    MASK_BLACK hides); use m.ref as mask=."""

    _name = "mask"
    _mode: Mode = "mask"

    def __init__(self, ref: Ref, doc: Builder) -> None:
        super().__init__(ref)
        self._doc: Final = doc

    def group(
        self, *, opacity: Num | None = None, transform: Affine | None = None
    ) -> AbstractContextManager[None]:
        """Wrap what is drawn inside in <g> with the given opacity and transform."""
        self._live()
        return self._group(optional(opacity=opacity, transform=transform))

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
        return add_linear(self._doc, "mask", stops, p0, p1, units)

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
        return add_radial(self._doc, "mask", stops, center, r, focus, units)


@final
class PatternSurface(PaintSurface[Paint]):
    """The inside of a `with s.pattern(w, h) as pat:` block, in pattern-local coordinates
    (0..w, 0..h) with theme paints; use pat.ref as a paint."""

    _name = "pattern"

    def path(self, d: Path, *, fill: Paint, **style: Unpack[Style]) -> None:
        """Draw `d` with any Style; see Canvas.path."""
        self._live()
        self._emit(d, {"fill": fill, **style_values(style, "path")})

    def group(self, **style: Unpack[Style]) -> AbstractContextManager[None]:
        """Wrap what is drawn inside in <g> with `style`; see Canvas.group."""
        self._live()
        return self._group(style_values(style, "group"))

"""The fluent SVG path-data builder, P()."""

import math
from typing import TYPE_CHECKING, Literal, Self, overload

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ._vec import Num, Point, angle, angle_pair, num, point

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

type Flag = bool | np.bool | Literal[0, 1]


def fmt(v: object, nd: int, what: str = "number") -> str:
    """`v` as SVG number text.

    Ints (Python or numpy) are written as they are; floats (numpy scalars included) with `nd`
    decimals, trailing zeros and a trailing point stripped, and -0 as 0. Raises TypeError for a
    bool or a non-number and ValueError for NaN or infinity; both messages start with `what`.
    """
    if type(v) is int:
        return str(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
    elif isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return str(int(v))
    else:
        raise TypeError(f"{what} takes a number, got {v!r}")
    if not math.isfinite(f):
        raise ValueError(f"{what} takes a finite number, got {v!r}")
    s = f"{f:.{nd}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def _flag(v: object, what: str) -> str:
    if isinstance(v, (bool, np.bool)):
        return "1" if bool(v) else "0"
    if isinstance(v, (int, np.integer)):
        if v == 0 or v == 1:
            return str(int(v))
        raise ValueError(f"{what} flags are 0 or 1, got {v!r}")
    raise TypeError(f"{what} flags are bools or 0 or 1, got {v!r}")


def _points(pts: ArrayLike, what: str) -> NDArray[np.float64]:
    """`pts` as an (N, 2) float array; (0, 2) for no points.

    Raises TypeError for non-numeric or boolean data and ValueError for another shape or a
    non-finite coordinate.
    """
    a: NDArray[np.generic] = np.asarray(pts)
    if a.size == 0:
        return np.zeros((0, 2))
    if a.dtype.kind not in "iuf":
        raise TypeError(f"{what} takes numeric points, got dtype {a.dtype}")
    if a.ndim != 2 or a.shape[1] != 2:
        raise ValueError(f"{what} takes points of shape (N, 2), got {a.shape}")
    f = np.asarray(a, dtype=np.float64)
    if not bool(np.isfinite(f).all()):
        raise ValueError(f"{what} takes finite points")
    return f


def ngon_vertices(c: Point, r: Num, n: int, a: Num, inner: Num | None) -> NDArray[np.float64]:
    """Vertices of a regular polygon, shape (n, 2), or a star, shape (2n, 2), around `c`.

    Vertex k sits at c + r (cos, sin)(a + 2 pi k / n), with `a` in screen radians. With `inner`,
    inner vertices at radius `inner` and angle a + pi (2k + 1) / n alternate with the outer ones.
    Raises ValueError for n < 3.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 3:
        raise ValueError(f"ngon takes n >= 3, got {n!r}")
    cx, cy = point(c, "ngon")
    rr, a0 = num(r, "ngon r"), num(a, "ngon angle")
    out: list[tuple[float, float]] = []
    ri = None if inner is None else num(inner, "ngon inner")
    for k in range(n):
        t = a0 + 2 * math.pi * k / n
        out.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
        if ri is not None:
            t = a0 + math.pi * (2 * k + 1) / n
            out.append((cx + ri * math.cos(t), cy + ri * math.sin(t)))
    return np.array(out, dtype=np.float64)


class Path:
    """A fluent builder for SVG path data in absolute commands; str() is the `d` attribute.

    Every method appends and returns the builder, and one builder holds any number of subpaths.
    Coordinates are written with `nd` decimals (see fmt).
    """

    def __init__(self, nd: int = 1) -> None:
        """Raises ValueError unless `nd` is an int from 0 to 4."""
        if isinstance(nd, bool) or not isinstance(nd, int) or not 0 <= nd <= 4:
            raise ValueError(f"nd takes 0 to 4 decimals, got {nd!r}")
        self._nd = nd
        self._parts: list[str] = []

    def __str__(self) -> str:
        return "".join(self._parts)

    def __repr__(self) -> str:
        return f"P({str(self)!r})"

    @property
    def empty(self) -> bool:
        """Whether nothing has been appended."""
        return len(self._parts) == 0

    def _n(self, v: object, what: str) -> str:
        return fmt(v, self._nd, what)

    def _xy(self, x: object, y: object, what: str) -> str:
        if y is None:
            if isinstance(x, (tuple, list, np.ndarray)):
                seq: tuple[object, ...] | list[object] | NDArray[np.generic] = x
                if len(seq) == 2:
                    return f"{self._n(seq[0], what)} {self._n(seq[1], what)}"
            raise TypeError(f"{what} takes x, y or a point (x, y), got {x!r}")
        return f"{self._n(x, what)} {self._n(y, what)}"

    def _pts(self, args: tuple[object, ...], n: int, what: str) -> str:
        """`args` as `n` points' text: 2n numbers, or n points."""
        if len(args) == 2 * n:
            return " ".join(self._n(v, what) for v in args)
        if len(args) == n:
            return " ".join(self._xy(p, None, what) for p in args)
        raise TypeError(f"{what} takes {2 * n} numbers or {n} points, got {len(args)} arguments")

    @overload
    def M(self, x: Num, y: Num, /) -> Self: ...
    @overload
    def M(self, p: Point, /) -> Self: ...
    def M(self, x: Num | Point, y: Num | None = None, /) -> Self:
        """Move to (x, y)."""
        self._parts.append("M" + self._xy(x, y, "M"))
        return self

    @overload
    def L(self, x: Num, y: Num, /) -> Self: ...
    @overload
    def L(self, p: Point, /) -> Self: ...
    def L(self, x: Num | Point, y: Num | None = None, /) -> Self:
        """Line to (x, y)."""
        self._parts.append("L" + self._xy(x, y, "L"))
        return self

    def H(self, x: Num, /) -> Self:
        """Horizontal line to x."""
        self._parts.append("H" + self._n(x, "H"))
        return self

    def V(self, y: Num, /) -> Self:
        """Vertical line to y."""
        self._parts.append("V" + self._n(y, "V"))
        return self

    @overload
    def C(self, x1: Num, y1: Num, x2: Num, y2: Num, x: Num, y: Num, /) -> Self: ...
    @overload
    def C(self, c1: Point, c2: Point, p: Point, /) -> Self: ...
    def C(self, *args: Num | Point) -> Self:
        """Cubic Bézier to the last point through control points 1 and 2."""
        self._parts.append("C" + self._pts(args, 3, "C"))
        return self

    @overload
    def Q(self, x1: Num, y1: Num, x: Num, y: Num, /) -> Self: ...
    @overload
    def Q(self, c: Point, p: Point, /) -> Self: ...
    def Q(self, *args: Num | Point) -> Self:
        """Quadratic Bézier to the last point through the control point."""
        self._parts.append("Q" + self._pts(args, 2, "Q"))
        return self

    @overload
    def A(
        self, rx: Num, ry: Num, rot: Num, large: Flag, sweep: Flag, x: Num, y: Num, /
    ) -> Self: ...
    @overload
    def A(self, rx: Num, ry: Num, rot: Num, large: Flag, sweep: Flag, p: Point, /) -> Self: ...
    def A(
        self,
        rx: Num,
        ry: Num,
        rot: Num,
        large: Flag,
        sweep: Flag,
        x: Num | Point,
        y: Num | None = None,
        /,
    ) -> Self:
        """Elliptical arc to (x, y); `rot` is the x-axis rotation in SVG degrees.

        Flags are bools, numpy bools, or ints equal to 0 or 1: another int raises ValueError
        and any other type TypeError.
        """
        radii = f"{self._n(rx, 'A')} {self._n(ry, 'A')} {self._n(rot, 'A')}"
        flags = f"{_flag(large, 'A')} {_flag(sweep, 'A')}"
        self._parts.append(f"A{radii} {flags} {self._xy(x, y, 'A')}")
        return self

    def Z(self) -> Self:
        """Close the subpath."""
        self._parts.append("Z")
        return self

    def rect(self, x: Num, y: Num, w: Num, h: Num) -> Self:
        """The rectangle with top-left (x, y). Raises ValueError for a negative w or h."""
        fx, fy, fw, fh = num(x, "rect x"), num(y, "rect y"), num(w, "rect w"), num(h, "rect h")
        if fw < 0 or fh < 0:
            raise ValueError(f"rect takes a non-negative size, got {w!r} x {h!r}")
        return self.M(fx, fy).H(fx + fw).V(fy + fh).H(fx).Z()

    def rrect(self, x: Num, y: Num, w: Num, h: Num, r: Num) -> Self:
        """The rectangle with corners rounded to radius min(r, w / 2, h / 2).

        Raises ValueError for a negative w, h or r.
        """
        fw, fh, fr = num(w, "rrect w"), num(h, "rrect h"), num(r, "rrect r")
        if fw < 0 or fh < 0 or fr < 0:
            raise ValueError(f"rrect takes a non-negative size and radius, got {w!r}, {h!r}, {r!r}")
        q = min(fr, fw / 2, fh / 2)
        if q == 0:
            return self.rect(x, y, w, h)
        fx, fy = num(x, "rrect x"), num(y, "rrect y")
        self.M(fx + q, fy).H(fx + fw - q).A(q, q, 0, 0, 1, fx + fw, fy + q)
        self.V(fy + fh - q).A(q, q, 0, 0, 1, fx + fw - q, fy + fh)
        self.H(fx + q).A(q, q, 0, 0, 1, fx, fy + fh - q)
        return self.V(fy + q).A(q, q, 0, 0, 1, fx + q, fy).Z()

    def _oval(self, c: Point, rx: float, ry: float, sweep: Literal[0, 1]) -> Self:
        # Snapped to the written grid so each half's ends are exactly 2 rx apart: a radius written
        # above half the chord turns each half into a large arc that bulges by about sqrt(2 r d).
        x, y = point(c, "circle")
        cx, cy, rx, ry = (round(v, self._nd) for v in (x, y, rx, ry))
        self.M(cx + rx, cy).A(rx, ry, 0, 1, sweep, cx - rx, cy)
        return self.A(rx, ry, 0, 1, sweep, cx + rx, cy).Z()

    def circle(self, c: Point, r: Num) -> Self:
        """The circle of radius `r` around `c`, as two arcs; nothing for r == 0.

        Raises ValueError for r < 0.
        """
        rr = num(r, "circle r")
        if rr < 0:
            raise ValueError(f"circle takes r >= 0, got {r!r}")
        return self if rr == 0 else self._oval(c, rr, rr, 1)

    def ellipse(self, c: Point, rx: Num, ry: Num) -> Self:
        """The axis-aligned ellipse around `c`; nothing when either radius is 0.

        Raises ValueError for a negative radius.
        """
        frx, fry = num(rx, "ellipse rx"), num(ry, "ellipse ry")
        if frx < 0 or fry < 0:
            raise ValueError(f"ellipse takes radii >= 0, got {rx!r}, {ry!r}")
        return self if frx == 0 or fry == 0 else self._oval(c, frx, fry, 1)

    def ring(self, c: Point, r0: Num, r1: Num) -> Self:
        """The annulus between radii r0 and r1: the outer circle, then the inner one drawn the
        other way round, so the default fill rule leaves the hole.

        Raises ValueError unless 0 <= r0 < r1.
        """
        f0, f1 = num(r0, "ring r0"), num(r1, "ring r1")
        if not 0 <= f0 < f1:
            raise ValueError(f"ring takes 0 <= r0 < r1, got {r0!r}, {r1!r}")
        self._oval(c, f1, f1, 1)
        return self if f0 == 0 else self._oval(c, f0, f0, 0)

    @staticmethod
    def _span(a0: float, a1: float, what: str) -> tuple[bool, bool]:
        """(large, sweep) for the arc from a0 to a1 (screen radians)."""
        if a0 == a1 or abs(a1 - a0) >= 2 * math.pi:
            raise ValueError(f"{what} takes a span above 0 and below a full turn, got {a0}..{a1}")
        return abs(a1 - a0) > math.pi, a1 > a0

    @overload
    def arc(self, c: Point, r: Num, *, deg: tuple[Num, Num]) -> Self: ...
    @overload
    def arc(self, c: Point, r: Num, *, rad: tuple[Num, Num]) -> Self: ...
    @overload
    def arc(self, c: Point, r: Num, *, bearing: tuple[Num, Num]) -> Self: ...
    def arc(
        self,
        c: Point,
        r: Num,
        *,
        deg: tuple[Num, Num] | None = None,
        rad: tuple[Num, Num] | None = None,
        bearing: tuple[Num, Num] | None = None,
    ) -> Self:
        """The circular arc of radius `r` around `c` from the first angle towards the second.

        Raises TypeError unless exactly one angle keyword is given, and ValueError when the
        angles are equal or at least a full turn apart.
        """
        a0, a1 = angle_pair(deg, rad, bearing, "arc")
        large, sweep = self._span(a0, a1, "arc")
        cx, cy = point(c, "arc")
        rr = num(r, "arc r")
        self.M(cx + rr * math.cos(a0), cy + rr * math.sin(a0))
        return self.A(rr, rr, 0, large, sweep, cx + rr * math.cos(a1), cy + rr * math.sin(a1))

    @overload
    def arc_band(self, c: Point, r0: Num, r1: Num, *, deg: tuple[Num, Num]) -> Self: ...
    @overload
    def arc_band(self, c: Point, r0: Num, r1: Num, *, rad: tuple[Num, Num]) -> Self: ...
    @overload
    def arc_band(self, c: Point, r0: Num, r1: Num, *, bearing: tuple[Num, Num]) -> Self: ...
    def arc_band(
        self,
        c: Point,
        r0: Num,
        r1: Num,
        *,
        deg: tuple[Num, Num] | None = None,
        rad: tuple[Num, Num] | None = None,
        bearing: tuple[Num, Num] | None = None,
    ) -> Self:
        """The closed annular sector between radii r0 and r1 from the first angle towards the
        second; a pie wedge when r0 == 0.

        Raises TypeError unless exactly one angle keyword is given, and ValueError unless
        0 <= r0 < r1 or for the spans arc() rejects.
        """
        a0, a1 = angle_pair(deg, rad, bearing, "arc_band")
        large, sweep = self._span(a0, a1, "arc_band")
        f0, f1 = num(r0, "arc_band r0"), num(r1, "arc_band r1")
        if not 0 <= f0 < f1:
            raise ValueError(f"arc_band takes 0 <= r0 < r1, got {r0!r}, {r1!r}")
        cx, cy = point(c, "arc_band")
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        if f0 == 0:
            self.M(cx, cy).L(cx + f1 * c0, cy + f1 * s0)
            return self.A(f1, f1, 0, large, sweep, cx + f1 * c1, cy + f1 * s1).Z()
        self.M(cx + f1 * c0, cy + f1 * s0).A(f1, f1, 0, large, sweep, cx + f1 * c1, cy + f1 * s1)
        self.L(cx + f0 * c1, cy + f0 * s1)
        return self.A(f0, f0, 0, large, not sweep, cx + f0 * c0, cy + f0 * s0).Z()

    @overload
    def ngon(self, c: Point, r: Num, n: int, *, deg: Num, inner: Num | None = None) -> Self: ...
    @overload
    def ngon(self, c: Point, r: Num, n: int, *, rad: Num, inner: Num | None = None) -> Self: ...
    @overload
    def ngon(self, c: Point, r: Num, n: int, *, bearing: Num, inner: Num | None = None) -> Self: ...
    def ngon(
        self,
        c: Point,
        r: Num,
        n: int,
        *,
        deg: Num | None = None,
        rad: Num | None = None,
        bearing: Num | None = None,
        inner: Num | None = None,
    ) -> Self:
        """A regular polygon (or with `inner`, a star) through ngon_vertices, first vertex at
        the given angle.

        Raises TypeError unless exactly one angle keyword is given, and ValueError for n < 3.
        """
        a = angle(deg, rad, bearing, "ngon")
        return self.poly(ngon_vertices(c, r, n, a, inner), closed=True)

    def dots(self, pts: ArrayLike, r: Num) -> Self:
        """One circle of radius `r` around each point of the (N, 2) `pts`."""
        rr = num(r, "dots r")
        if rr < 0:
            raise ValueError(f"dots takes r >= 0, got {r!r}")
        if rr == 0:
            return self
        for x, y in _points(pts, "dots").tolist():
            self._oval((x, y), rr, rr, 1)
        return self

    @overload
    def arrowhead(self, tip: Point, size: Num, *, deg: Num, width: Num | None = None) -> Self: ...
    @overload
    def arrowhead(self, tip: Point, size: Num, *, rad: Num, width: Num | None = None) -> Self: ...
    @overload
    def arrowhead(
        self, tip: Point, size: Num, *, bearing: Num, width: Num | None = None
    ) -> Self: ...
    def arrowhead(
        self,
        tip: Point,
        size: Num,
        *,
        deg: Num | None = None,
        rad: Num | None = None,
        bearing: Num | None = None,
        width: Num | None = None,
    ) -> Self:
        """A triangle with its point at `tip`, pointing along the angle, `size` long and
        2 * width wide at the base (width defaults to 0.3 * size).

        Raises TypeError unless exactly one angle keyword is given.
        """
        a = angle(deg, rad, bearing, "arrowhead")
        tx, ty = point(tip, "arrowhead")
        fs = num(size, "arrowhead size")
        w = 0.3 * fs if width is None else num(width, "arrowhead width")
        bx, by = tx - fs * math.cos(a), ty - fs * math.sin(a)
        nx, ny = -w * math.sin(a), w * math.cos(a)
        return self.M(tx, ty).L(bx + nx, by + ny).L(bx - nx, by - ny).Z()

    def poly(self, pts: ArrayLike, *, closed: bool = False) -> Self:
        """The polyline through the (N, 2) `pts`, closed with Z when `closed`; nothing for no
        points.

        Raises ValueError for another shape or a non-finite coordinate.
        """
        rows = _points(pts, "poly").tolist()
        if len(rows) == 0:
            return self
        n = self._n
        self._parts.extend(
            f"{'L' if i > 0 else 'M'}{n(x, 'poly')} {n(y, 'poly')}" for i, (x, y) in enumerate(rows)
        )
        return self.Z() if closed else self

    def spline(self, pts: ArrayLike, *, closed: bool = False, tension: Num = 1.0) -> Self:
        """A Catmull-Rom curve through the (N, 2) `pts` as cubic Béziers, control points offset
        by tension / 6 of the neighbour chord.

        An open curve's end segments repeat their end point; fewer than 3 points give poly().
        """
        p: list[list[float]] = _points(pts, "spline").tolist()
        k = num(tension, "spline tension") / 6
        n = len(p)
        if n < 3:
            return self.poly(pts, closed=closed)
        self.M(p[0][0], p[0][1])
        for i in range(n if closed else n - 1):
            p0 = p[(i - 1) % n] if (closed or i > 0) else p[0]
            p1, p2 = p[i], p[(i + 1) % n]
            p3 = p[(i + 2) % n] if (closed or i + 2 < n) else p2
            self.C(
                p1[0] + (p2[0] - p0[0]) * k,
                p1[1] + (p2[1] - p0[1]) * k,
                p2[0] - (p3[0] - p1[0]) * k,
                p2[1] - (p3[1] - p1[1]) * k,
                p2[0],
                p2[1],
            )
        return self.Z() if closed else self

    def shape(self, geom: "BaseGeometry") -> Self:
        """Any shapely geometry as subpaths.

        A Polygon gives its exterior and each hole as closed subpaths wound opposite ways
        (orient(g, 1.0)), so holes show under the default fill rule; a LinearRing is closed and
        a LineString open; Multi* and GeometryCollection draw part by part in order; points
        and empty geometries draw nothing. A ring's repeated closing coordinate becomes Z.
        """
        from shapely.geometry import LinearRing, LineString, Polygon
        from shapely.geometry.base import BaseMultipartGeometry
        from shapely.geometry.polygon import orient

        if geom.is_empty:
            return self
        if isinstance(geom, Polygon):
            g = orient(geom, 1.0)
            self._ring(np.asarray(g.exterior.coords))
            for hole in g.interiors:
                self._ring(np.asarray(hole.coords))
        elif isinstance(geom, LinearRing):
            self._ring(np.asarray(geom.coords))
        elif isinstance(geom, LineString):
            self.poly(np.asarray(geom.coords)[:, :2])
        elif isinstance(geom, BaseMultipartGeometry):
            for part in geom.geoms:
                self.shape(part)
        return self

    def _ring(self, coords: NDArray[np.float64]) -> None:
        xy = coords[:, :2]
        if len(xy) > 1 and np.array_equal(xy[0], xy[-1]):
            xy = xy[:-1]
        self.poly(xy, closed=True)


def P(nd: int = 1) -> Path:
    """A new, empty Path writing coordinates with `nd` decimals (0 to 4)."""
    return Path(nd)

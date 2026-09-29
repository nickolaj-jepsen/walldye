"""Numbers, points, vectors, rectangles, angles and ufunc-safe scalar maths."""

import math
from typing import Final, NamedTuple, TypeIs, overload, override

import numpy as np
from numpy.typing import ArrayLike, NDArray

type Num = float | np.integer | np.floating
type Point = tuple[Num, Num]
type Array = NDArray[np.integer | np.floating]

# The runtime counterpart of Num; bool is an int, so every check excludes it separately.
NUM_TYPES: Final = (int, float, np.integer, np.floating)


def real(v: object, what: str) -> float:
    """`v` as a float.

    Raises TypeError unless `v` is an int, float or numpy integer or float scalar; a bool is
    not a number here. The message starts with `what`.
    """
    if type(v) is float:  # the hot case: every coordinate passes through here
        return v
    if isinstance(v, bool) or not isinstance(v, NUM_TYPES):
        raise TypeError(f"{what} takes a number, got {v!r}")
    return float(v)


def num(v: object, what: str) -> float:
    """`v` as a finite float.

    Raises what real() raises, and ValueError when `v` is NaN or infinite.
    """
    f = v if type(v) is float else real(v, what)
    if not math.isfinite(f):
        raise ValueError(f"{what} takes a finite number, got {v!r}")
    return f


def point(p: object, what: str) -> tuple[float, float]:
    """`p`, a pair of numbers (a tuple, Vec, list or shape-(2,) array), as two finite floats.

    Raises TypeError for anything that is not a pair of numbers and ValueError for NaN or
    infinity.
    """
    if isinstance(p, np.ndarray):
        arr: NDArray[np.generic] = p
        if arr.shape != (2,):
            raise TypeError(f"{what} takes a point (x, y), got an array of shape {arr.shape}")
        x, y = arr[0], arr[1]
    elif isinstance(p, (tuple, list)):
        pair: tuple[object, ...] | list[object] = p
        if len(pair) != 2:
            raise TypeError(f"{what} takes a point (x, y), got {pair!r}")
        x, y = pair
    else:
        raise TypeError(f"{what} takes a point (x, y), got {p!r}")
    return num(x, what), num(y, what)


class Vec(NamedTuple):
    """A 2D point or vector in canvas pixels; unpacks like the tuple (x, y).

    Arithmetic with points and numbers gives a Vec; with an ndarray on either side it gives the
    ndarray of the same operation on np.asarray(self). Any other operand gets NotImplemented,
    so Python raises its TypeError; a pair holding NaN or infinity raises ValueError.
    """

    x: float
    y: float

    # numpy arrays and scalars hand their operators to Vec's reflected ones.
    __array_priority__ = 1000.0

    @overload
    def __add__(self, o: Point, /) -> "Vec": ...  # pyrefly: ignore[bad-override]
    @overload
    def __add__(self, o: Array, /) -> NDArray[np.float64]: ...
    @override
    def __add__(self, o: Point | Array, /) -> "Vec | NDArray[np.float64]":
        if isinstance(o, np.ndarray):
            return _array(np.asarray(self) + o)
        if (p := _pair(o, "Vec +")) is None:
            return NotImplemented
        return Vec(self.x + p[0], self.y + p[1])

    @overload
    def __radd__(self, o: Point, /) -> "Vec": ...
    @overload
    def __radd__(self, o: Array, /) -> NDArray[np.float64]: ...
    def __radd__(self, o: Point | Array, /) -> "Vec | NDArray[np.float64]":
        if isinstance(o, np.ndarray):
            return _array(o + np.asarray(self))
        if (p := _pair(o, "Vec +")) is None:
            return NotImplemented
        return Vec(p[0] + self.x, p[1] + self.y)

    @overload
    def __sub__(self, o: Point, /) -> "Vec": ...
    @overload
    def __sub__(self, o: Array, /) -> NDArray[np.float64]: ...
    def __sub__(self, o: Point | Array, /) -> "Vec | NDArray[np.float64]":
        if isinstance(o, np.ndarray):
            return _array(np.asarray(self) - o)
        if (p := _pair(o, "Vec -")) is None:
            return NotImplemented
        return Vec(self.x - p[0], self.y - p[1])

    @overload
    def __rsub__(self, o: Point, /) -> "Vec": ...
    @overload
    def __rsub__(self, o: Array, /) -> NDArray[np.float64]: ...
    def __rsub__(self, o: Point | Array, /) -> "Vec | NDArray[np.float64]":
        if isinstance(o, np.ndarray):
            return _array(o - np.asarray(self))
        if (p := _pair(o, "Vec -")) is None:
            return NotImplemented
        return Vec(p[0] - self.x, p[1] - self.y)

    @overload
    def __mul__(self, k: Num, /) -> "Vec": ...  # pyrefly: ignore[bad-override]
    @overload
    def __mul__(self, k: Array, /) -> NDArray[np.float64]: ...
    @override
    def __mul__(self, k: Num | Array, /) -> "Vec | NDArray[np.float64]":
        if isinstance(k, np.ndarray):
            return _array(np.asarray(self) * k)
        if not _is_number(k):
            return NotImplemented
        f = float(k)
        return Vec(self.x * f, self.y * f)

    @overload
    def __rmul__(self, k: Num, /) -> "Vec": ...  # pyrefly: ignore[bad-override]
    @overload
    def __rmul__(self, k: Array, /) -> NDArray[np.float64]: ...
    @override
    def __rmul__(self, k: Num | Array, /) -> "Vec | NDArray[np.float64]":
        if isinstance(k, np.ndarray):
            return _array(k * np.asarray(self))
        if not _is_number(k):
            return NotImplemented
        f = float(k)
        return Vec(f * self.x, f * self.y)

    @overload
    def __truediv__(self, k: Num, /) -> "Vec": ...
    @overload
    def __truediv__(self, k: Array, /) -> NDArray[np.float64]: ...
    def __truediv__(self, k: Num | Array, /) -> "Vec | NDArray[np.float64]":
        if isinstance(k, np.ndarray):
            return _array(np.asarray(self) / np.asarray(k, dtype=np.float64))
        if not _is_number(k):
            return NotImplemented
        f = float(k)
        return Vec(self.x / f, self.y / f)

    def __rtruediv__(self, o: Array, /) -> NDArray[np.float64]:
        """Only for an ndarray divided by a Vec; a number divided by a Vec is a TypeError."""
        if isinstance(o, np.ndarray):
            return _array(np.asarray(o, dtype=np.float64) / np.asarray(self))
        return NotImplemented

    def __neg__(self) -> "Vec":
        return Vec(-float(self.x), -float(self.y))

    def __abs__(self) -> float:
        """The length."""
        return math.hypot(self.x, self.y)

    def dot(self, o: Point) -> float:
        """The dot product with `o`."""
        x, y = point(o, "Vec.dot")
        return self.x * x + self.y * y

    def perp(self) -> "Vec":
        """(-y, x): this vector turned a quarter turn clockwise on screen."""
        return Vec(-float(self.y), float(self.x))

    def unit(self) -> "Vec":
        """This vector scaled to length 1. Raises ValueError for the zero vector."""
        n = math.hypot(self.x, self.y)
        if n == 0:
            raise ValueError("the zero vector has no direction")
        return Vec(self.x / n, self.y / n)

    @overload
    def rotate(self, *, deg: Num, about: Point = (0.0, 0.0)) -> "Vec": ...
    @overload
    def rotate(self, *, rad: Num, about: Point = (0.0, 0.0)) -> "Vec": ...
    def rotate(
        self, *, deg: Num | None = None, rad: Num | None = None, about: Point = (0.0, 0.0)
    ) -> "Vec":
        """This point turned clockwise on screen by the angle about `about`.

        Raises TypeError unless exactly one of deg= and rad= is given.
        """
        a = angle(deg, rad, None, "Vec.rotate")
        cx, cy = point(about, "Vec.rotate about")
        c, s = math.cos(a), math.sin(a)
        dx, dy = self.x - cx, self.y - cy
        return Vec(cx + dx * c - dy * s, cy + dx * s + dy * c)


def _array(v: object) -> NDArray[np.float64]:
    return np.asarray(v, dtype=np.float64)


def _is_number(v: object) -> TypeIs[int | float | np.integer | np.floating]:
    return not isinstance(v, bool) and isinstance(v, NUM_TYPES)


def _pair(o: object, what: str) -> tuple[float, float] | None:
    """`o` as two finite floats when it is a tuple or list of two numbers, else None.

    Raises ValueError when such a pair holds NaN or infinity.
    """
    if not isinstance(o, (tuple, list)):
        return None
    pair: tuple[object, ...] | list[object] = o
    if len(pair) != 2:
        return None
    x, y = pair
    if not (_is_number(x) and _is_number(y)):
        return None
    return num(x, what), num(y, what)


class Rect(NamedTuple):
    """An axis-aligned rectangle: top-left (x, y), width w and height h."""

    x: float
    y: float
    w: float
    h: float

    @property
    def x1(self) -> float:
        """The right edge, x + w."""
        return self.x + self.w

    @property
    def y1(self) -> float:
        """The bottom edge, y + h."""
        return self.y + self.h

    @property
    def center(self) -> Vec:
        """The center point."""
        return Vec(self.x + self.w / 2, self.y + self.h / 2)

    def frac(self, fx: Num, fy: Num) -> Vec:
        """The point (x + fx * w, y + fy * h)."""
        return Vec(self.x + num(fx, "Rect.frac") * self.w, self.y + num(fy, "Rect.frac") * self.h)

    def contains(self, p: Point, margin: Num = 0.0) -> bool:
        """Whether `p` lies in the rectangle grown by `margin` on every side, edges included."""
        x, y = point(p, "Rect.contains")
        m = num(margin, "Rect.contains margin")
        return self.x - m <= x <= self.x1 + m and self.y - m <= y <= self.y1 + m


def angle(deg: object, rad: object, bearing: object, what: str = "angle") -> float:
    """The one angle given as deg=, rad= or bearing=, in screen radians (clockwise from east).

    `bearing` is degrees clockwise from north, so bearing=b equals deg=b - 90. Raises TypeError
    unless exactly one is not None, or when it is not a number (see real()); ValueError for NaN
    or infinity.
    """
    given = [(k, v) for k, v in (("deg", deg), ("rad", rad), ("bearing", bearing)) if v is not None]
    if len(given) != 1:
        names = ", ".join(f"{k}=" for k, _ in given) if len(given) > 0 else "none"
        raise TypeError(f"{what} takes exactly one of deg=, rad= or bearing= (got {names})")
    unit, v = given[0]
    f = num(v, f"{what} {unit}=")
    if unit == "rad":
        return f
    return math.radians(f if unit == "deg" else f - 90)


def angle_pair(deg: object, rad: object, bearing: object, what: str) -> tuple[float, float]:
    """The one angle range given as deg=(a0, a1), rad= or bearing=, in screen radians.

    Raises as angle() does, and TypeError when the value is not a pair.
    """
    given = [(k, v) for k, v in (("deg", deg), ("rad", rad), ("bearing", bearing)) if v is not None]
    if len(given) != 1:
        names = ", ".join(f"{k}=" for k, _ in given) if len(given) > 0 else "none"
        raise TypeError(f"{what} takes exactly one of deg=, rad= or bearing= (got {names})")
    unit, v = given[0]
    a0, a1 = point(v, f"{what} {unit}=")
    if unit == "rad":
        return a0, a1
    if unit == "deg":
        return math.radians(a0), math.radians(a1)
    return math.radians(a0 - 90), math.radians(a1 - 90)


@overload
def polar(c: Point, r: Num, *, deg: Num) -> Vec: ...
@overload
def polar(c: Point, r: Num, *, rad: Num) -> Vec: ...
@overload
def polar(c: Point, r: Num, *, bearing: Num) -> Vec: ...
def polar(
    c: Point,
    r: Num,
    *,
    deg: Num | None = None,
    rad: Num | None = None,
    bearing: Num | None = None,
) -> Vec:
    """The point at distance `r` from `c` in the given direction.

    Raises TypeError unless exactly one of deg=, rad= and bearing= is given.
    """
    a = angle(deg, rad, bearing, "polar")
    cx, cy = point(c, "polar")
    rr = num(r, "polar r")
    return Vec(cx + rr * math.cos(a), cy + rr * math.sin(a))


def _is_real(v: object) -> TypeIs[int | float | np.integer | np.floating]:
    return isinstance(v, NUM_TYPES)


@overload
def lerp(a: Num, b: Num, t: Num) -> float: ...
@overload
def lerp(a: ArrayLike, b: ArrayLike, t: ArrayLike) -> NDArray[np.float64]: ...
def lerp(a: ArrayLike, b: ArrayLike, t: ArrayLike) -> float | NDArray[np.float64]:
    """a + (b - a) * t: a float for numbers, element-wise float64 for arrays."""
    if _is_real(a) and _is_real(b) and _is_real(t):
        fa, fb, ft = float(a), float(b), float(t)
        return fa + (fb - fa) * ft
    xa, xb, xt = _arr(a), _arr(b), _arr(t)
    return xa + (xb - xa) * xt


@overload
def clamp(v: Num, lo: Num = 0.0, hi: Num = 1.0) -> float: ...
@overload
def clamp(v: ArrayLike, lo: ArrayLike = 0.0, hi: ArrayLike = 1.0) -> NDArray[np.float64]: ...
def clamp(v: ArrayLike, lo: ArrayLike = 0.0, hi: ArrayLike = 1.0) -> float | NDArray[np.float64]:
    """`v` limited to [lo, hi]: `lo if v < lo else min(v, hi)` for numbers, np.clip for arrays."""
    if _is_real(v) and _is_real(lo) and _is_real(hi):
        fv, flo, fhi = float(v), float(lo), float(hi)
        return flo if fv < flo else min(fv, fhi)
    return np.asarray(np.clip(_arr(v), _arr(lo), _arr(hi)), dtype=np.float64)


@overload
def smoothstep(e0: Num, e1: Num, x: Num) -> float: ...
@overload
def smoothstep(e0: ArrayLike, e1: ArrayLike, x: ArrayLike) -> NDArray[np.float64]: ...
def smoothstep(e0: ArrayLike, e1: ArrayLike, x: ArrayLike) -> float | NDArray[np.float64]:
    """Hermite ease from 0 at `e0` to 1 at `e1`: t = clamp((x - e0) / (e1 - e0)), t * t * (3 - 2t).

    Works with e0 > e1 (a falling edge). Raises ValueError when e0 == e1.
    """
    if _is_real(e0) and _is_real(e1) and _is_real(x):
        f0, f1, fx = float(e0), float(e1), float(x)
        if f0 == f1:
            raise ValueError(f"smoothstep needs e0 != e1, got {f0} twice")
        t = clamp((fx - f0) / (f1 - f0))
        return t * t * (3 - 2 * t)
    a0, a1, ax = _arr(e0), _arr(e1), _arr(x)
    if bool(np.any(a0 == a1)):
        raise ValueError("smoothstep needs e0 != e1")
    t = np.clip((ax - a0) / (a1 - a0), 0.0, 1.0)
    return np.asarray(t * t * (3 - 2 * t), dtype=np.float64)


def _arr(v: ArrayLike) -> NDArray[np.float64]:
    return np.asarray(v, dtype=np.float64)

"""2D affine transforms in SVG's matrix(a b c d e f) form."""

import math
from dataclasses import dataclass
from typing import Self, final, overload

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ._vec import Num, Point, Vec, angle, num, point


@final
@dataclass(frozen=True, slots=True)
class Affine:
    """The map x' = a x + c y + e, y' = b x + d y + f; also the type of `transform=`.

    Every field is a finite float: construction raises TypeError for a non-number (or bool)
    and ValueError for NaN or infinity.
    """

    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    def __post_init__(self) -> None:
        for name in ("a", "b", "c", "d", "e", "f"):
            object.__setattr__(self, name, num(getattr(self, name), f"Affine {name}"))

    @classmethod
    def identity(cls) -> Self:
        """The map that leaves every point where it is."""
        return cls(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    @classmethod
    def translate(cls, dx: Num, dy: Num) -> Self:
        """Shift by (dx, dy)."""
        return cls(1.0, 0.0, 0.0, 1.0, num(dx, "translate"), num(dy, "translate"))

    @classmethod
    def scale(cls, sx: Num, sy: Num | None = None, *, about: Point = (0.0, 0.0)) -> Self:
        """Scale by sx horizontally and sy (default sx) vertically, keeping `about` fixed."""
        fx = num(sx, "scale")
        fy = fx if sy is None else num(sy, "scale")
        ox, oy = point(about, "scale about")
        return cls(fx, 0.0, 0.0, fy, ox - fx * ox, oy - fy * oy)

    @overload
    @classmethod
    def rotate(cls, *, deg: Num, about: Point = (0.0, 0.0)) -> Self: ...
    @overload
    @classmethod
    def rotate(cls, *, rad: Num, about: Point = (0.0, 0.0)) -> Self: ...
    @classmethod
    def rotate(
        cls, *, deg: Num | None = None, rad: Num | None = None, about: Point = (0.0, 0.0)
    ) -> Self:
        """Turn clockwise on screen by the angle about `about`.

        Raises TypeError unless exactly one of deg= and rad= is given.
        """
        t = angle(deg, rad, None, "Affine.rotate")
        co, si = math.cos(t), math.sin(t)
        ox, oy = point(about, "Affine.rotate about")
        return cls(co, si, -si, co, ox - co * ox + si * oy, oy - si * ox - co * oy)

    @overload
    @classmethod
    def frame(cls, origin: Point, *, deg: Num, scale: Num = 1.0) -> Self: ...
    @overload
    @classmethod
    def frame(cls, origin: Point, *, rad: Num, scale: Num = 1.0) -> Self: ...
    @overload
    @classmethod
    def frame(cls, origin: Point, *, bearing: Num, scale: Num = 1.0) -> Self: ...
    @classmethod
    def frame(
        cls,
        origin: Point,
        *,
        deg: Num | None = None,
        rad: Num | None = None,
        bearing: Num | None = None,
        scale: Num = 1.0,
    ) -> Self:
        """Local coordinates to the canvas: local +x points in the given direction, local +y a
        quarter turn clockwise from it, both scaled by `scale`, and local (0, 0) lands on
        `origin`.

        Raises TypeError unless exactly one angle keyword is given.
        """
        t = angle(deg, rad, bearing, "Affine.frame")
        k = num(scale, "Affine.frame scale")
        co, si = k * math.cos(t), k * math.sin(t)
        ox, oy = point(origin, "Affine.frame origin")
        return cls(co, si, -si, co, ox, oy)

    def __matmul__(self, o: "Affine") -> "Affine":
        """The composition applying `o` first: (m @ n)(p) == m(n(p))."""
        if not isinstance(o, Affine):
            return NotImplemented
        return Affine(
            self.a * o.a + self.c * o.b,
            self.b * o.a + self.d * o.b,
            self.a * o.c + self.c * o.d,
            self.b * o.c + self.d * o.d,
            self.a * o.e + self.c * o.f + self.e,
            self.b * o.e + self.d * o.f + self.f,
        )

    def __call__(self, p: Point) -> Vec:
        """The image of one point."""
        x, y = point(p, "Affine")
        return Vec(self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def apply(self, pts: ArrayLike) -> NDArray[np.float64]:
        """The images of the (N, 2) `pts`, as an (N, 2) array.

        Raises ValueError for another shape.
        """
        xy = np.asarray(pts, dtype=np.float64)
        if xy.size == 0:
            return np.zeros((0, 2))
        if xy.ndim != 2 or xy.shape[1] != 2:
            raise ValueError(f"apply takes points of shape (N, 2), got {xy.shape}")
        x, y = xy[:, 0], xy[:, 1]
        return np.stack([self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f], 1)

    def inverse(self) -> "Affine":
        """The map undoing this one. Raises ValueError when it is singular."""
        det = self.a * self.d - self.b * self.c
        if det == 0:
            raise ValueError(f"{self!r} is singular")
        return Affine(
            self.d / det,
            -self.b / det,
            -self.c / det,
            self.a / det,
            (self.c * self.f - self.d * self.e) / det,
            (self.b * self.e - self.a * self.f) / det,
        )

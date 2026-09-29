"""Seeded 2D and 3D Perlin noise, scalar or vectorized with identical arithmetic."""

import math
import random
from typing import Final, final, overload

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ._vec import NUM_TYPES, Num, real

type _F = NDArray[np.float64]
type _I = NDArray[np.int64]


def _fade(t: float) -> float:
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _grad2(h: int, x: float, y: float) -> float:
    h &= 7
    u, v = (x, y) if h < 4 else (y, x)
    return (u if h & 1 == 0 else -u) + (2 * v if h & 2 == 0 else -2 * v)


def _grad3(h: int, x: float, y: float, z: float) -> float:
    h &= 15
    a = x if h < 8 else y
    b = y if h < 4 else (x if h in (12, 14) else z)
    return (a if h & 1 == 0 else -a) + (b if h & 2 == 0 else -b)


def _fade_a(t: _F) -> _F:
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp_a(a: _F, b: _F, t: _F) -> _F:
    return a + (b - a) * t


def _grad2_a(h: _I, x: _F, y: _F) -> _F:
    h = h & 7
    swap = h >= 4
    u: _F = np.where(swap, y, x)
    v: _F = np.where(swap, x, y)
    gu: _F = np.where(h & 1 == 0, u, -u)
    gv: _F = np.where(h & 2 == 0, 2 * v, -2 * v)
    return gu + gv


def _grad3_a(h: _I, x: _F, y: _F, z: _F) -> _F:
    h = h & 15
    a: _F = np.where(h < 8, x, y)
    pick_x: NDArray[np.bool] = (h == 12) | (h == 14)
    xz: _F = np.where(pick_x, x, z)
    b: _F = np.where(h < 4, y, xz)
    ga: _F = np.where(h & 1 == 0, a, -a)
    gb: _F = np.where(h & 2 == 0, b, -b)
    return ga + gb


def _scalar(*vs: object) -> bool:
    return all(isinstance(v, NUM_TYPES) for v in vs)


def _arrays(*vs: ArrayLike) -> list[_F]:
    return [np.asarray(a, dtype=np.float64) for a in np.broadcast_arrays(*vs)]


@final
class Noise:
    """Seeded Perlin gradient noise, roughly within [-1, 1].

    The permutation is list(range(256)) shuffled by random.Random(seed), doubled. Numbers in
    give a float out; arrays in broadcast and give float64 arrays whose every element equals
    the scalar result for the same inputs.
    """

    def __init__(self, seed: int | str) -> None:
        """Raises TypeError unless `seed` is an int (not a bool) or a str."""
        if isinstance(seed, bool) or not isinstance(seed, (int, str)):
            raise TypeError(f"Noise takes an int or str seed, got {seed!r}")
        p = list(range(256))
        random.Random(seed).shuffle(p)
        self._p: Final[list[int]] = p + p
        self._pa: Final[_I] = np.array(self._p, dtype=np.int64)

    @overload
    def __call__(self, x: Num, y: Num) -> float: ...
    @overload
    def __call__(self, x: ArrayLike, y: ArrayLike) -> _F: ...
    def __call__(self, x: ArrayLike, y: ArrayLike) -> float | _F:
        """2D noise at (x, y)."""
        if _scalar(x, y):
            return self._n2(x, y)
        ax, ay = _arrays(x, y)
        return self._n2a(ax, ay)

    def _n2(self, x: object, y: object) -> float:
        p = self._p
        fx, fy = real(x, "noise"), real(y, "noise")
        xi, yi = math.floor(fx), math.floor(fy)
        xf, yf = fx - xi, fy - yi
        xi &= 255
        yi &= 255
        u, v = _fade(xf), _fade(yf)
        aa, ab = p[p[xi] + yi], p[p[xi] + yi + 1]
        ba, bb = p[p[xi + 1] + yi], p[p[xi + 1] + yi + 1]
        x1 = _lerp(_grad2(aa, xf, yf), _grad2(ba, xf - 1, yf), u)
        x2 = _lerp(_grad2(ab, xf, yf - 1), _grad2(bb, xf - 1, yf - 1), u)
        return float(_lerp(x1, x2, v) * 0.5)

    def _n2a(self, x: _F, y: _F) -> _F:
        p = self._pa
        fx: _F = np.floor(x)
        fy: _F = np.floor(y)
        xf, yf = x - fx, y - fy
        xi, yi = fx.astype(np.int64) & 255, fy.astype(np.int64) & 255
        u, v = _fade_a(xf), _fade_a(yf)
        aa, ab = p[p[xi] + yi], p[p[xi] + yi + 1]
        ba, bb = p[p[xi + 1] + yi], p[p[xi + 1] + yi + 1]
        x1 = _lerp_a(_grad2_a(aa, xf, yf), _grad2_a(ba, xf - 1, yf), u)
        x2 = _lerp_a(_grad2_a(ab, xf, yf - 1), _grad2_a(bb, xf - 1, yf - 1), u)
        return _lerp_a(x1, x2, v) * 0.5

    @overload
    def n3(self, x: Num, y: Num, z: Num) -> float: ...
    @overload
    def n3(self, x: ArrayLike, y: ArrayLike, z: ArrayLike) -> _F: ...
    def n3(self, x: ArrayLike, y: ArrayLike, z: ArrayLike) -> float | _F:
        """3D noise at (x, y, z)."""
        if _scalar(x, y, z):
            return self._n3(x, y, z)
        ax, ay, az = _arrays(x, y, z)
        return self._n3a(ax, ay, az)

    def _n3(self, x: object, y: object, z: object) -> float:
        p = self._p
        fx, fy, fz = real(x, "noise"), real(y, "noise"), real(z, "noise")
        xi, yi, zi = math.floor(fx) & 255, math.floor(fy) & 255, math.floor(fz) & 255
        xf, yf, zf = fx - math.floor(fx), fy - math.floor(fy), fz - math.floor(fz)
        u, v, w = _fade(xf), _fade(yf), _fade(zf)
        a, b = p[xi] + yi, p[xi + 1] + yi
        aa, ab, ba, bb = p[a] + zi, p[a + 1] + zi, p[b] + zi, p[b + 1] + zi
        g = _grad3
        return float(
            _lerp(
                _lerp(
                    _lerp(g(p[aa], xf, yf, zf), g(p[ba], xf - 1, yf, zf), u),
                    _lerp(g(p[ab], xf, yf - 1, zf), g(p[bb], xf - 1, yf - 1, zf), u),
                    v,
                ),
                _lerp(
                    _lerp(g(p[aa + 1], xf, yf, zf - 1), g(p[ba + 1], xf - 1, yf, zf - 1), u),
                    _lerp(
                        g(p[ab + 1], xf, yf - 1, zf - 1), g(p[bb + 1], xf - 1, yf - 1, zf - 1), u
                    ),
                    v,
                ),
                w,
            )
        )

    def _n3a(self, x: _F, y: _F, z: _F) -> _F:
        p = self._pa
        fx: _F = np.floor(x)
        fy: _F = np.floor(y)
        fz: _F = np.floor(z)
        xi, yi, zi = (
            fx.astype(np.int64) & 255,
            fy.astype(np.int64) & 255,
            fz.astype(np.int64) & 255,
        )
        xf, yf, zf = x - fx, y - fy, z - fz
        u, v, w = _fade_a(xf), _fade_a(yf), _fade_a(zf)
        a, b = p[xi] + yi, p[xi + 1] + yi
        aa, ab, ba, bb = p[a] + zi, p[a + 1] + zi, p[b] + zi, p[b + 1] + zi
        g, lerp = _grad3_a, _lerp_a
        return lerp(
            lerp(
                lerp(g(p[aa], xf, yf, zf), g(p[ba], xf - 1, yf, zf), u),
                lerp(g(p[ab], xf, yf - 1, zf), g(p[bb], xf - 1, yf - 1, zf), u),
                v,
            ),
            lerp(
                lerp(g(p[aa + 1], xf, yf, zf - 1), g(p[ba + 1], xf - 1, yf, zf - 1), u),
                lerp(g(p[ab + 1], xf, yf - 1, zf - 1), g(p[bb + 1], xf - 1, yf - 1, zf - 1), u),
                v,
            ),
            w,
        )

    @overload
    def fbm(
        self, x: Num, y: Num, octaves: int = 4, lacunarity: Num = 2.0, gain: Num = 0.5
    ) -> float: ...
    @overload
    def fbm(
        self, x: ArrayLike, y: ArrayLike, octaves: int = 4, lacunarity: Num = 2.0, gain: Num = 0.5
    ) -> _F: ...
    def fbm(
        self, x: ArrayLike, y: ArrayLike, octaves: int = 4, lacunarity: Num = 2.0, gain: Num = 0.5
    ) -> float | _F:
        """Fractal sum of `octaves` layers of 2D noise, each `lacunarity` times finer and `gain`
        times weaker, normalized by the total weight."""
        lac, g = real(lacunarity, "noise"), real(gain, "noise")
        amp, freq, norm = 1.0, 1.0, 0.0
        if _scalar(x, y):
            fx, fy = real(x, "noise"), real(y, "noise")
            total = 0.0
            for _ in range(octaves):
                total += amp * self._n2(fx * freq, fy * freq)
                norm += amp
                amp *= g
                freq *= lac
            return total / norm
        ax, ay = _arrays(x, y)
        acc: _F = np.zeros(ax.shape)
        for _ in range(octaves):
            acc = acc + amp * self._n2a(ax * freq, ay * freq)
            norm += amp
            amp *= g
            freq *= lac
        return acc / norm

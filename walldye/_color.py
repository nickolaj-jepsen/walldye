"""Symbolic colors: formulas over theme tokens, resolved to hex only under a theme.

A formula is a tuple, fixed because hashes depend on it: a token is (0, i) with i its index in
TOKENS, a mask constant (1, level) with level 0 or 255, a mix (2, a, b, t) and a regime
choice (3, dark, light). It holds only ints, floats and nested colors, so hashes do not change
with PYTHONHASHSEED.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Final, Literal, NoReturn, Self, final, overload, override

import numpy as np
from numpy.typing import NDArray

from ._theme import TOKENS, Coefs, blend_coefs, is_light, token_coefs
from ._theme import mix as hex_mix
from ._vec import Num, real

type _Formula = (
    tuple[Literal[0], int]
    | tuple[Literal[1], int]
    | tuple[Literal[2], "Color", "Color", float]
    | tuple[Literal[2], "MaskColor", "MaskColor", float]
    | tuple[Literal[3], "Color", "Color"]
)


class _Symbolic:
    """The shared behavior of Color and MaskColor: immutable, equal and hashed by formula,
    unordered and without a text form."""

    __slots__ = ("_formula", "_hash")
    _formula: _Formula
    _hash: int

    def __init__(self, formula: _Formula) -> None:
        """Internal: colors come from the tokens, mix, ramp, ladder and by_regime."""
        object.__setattr__(self, "_formula", formula)
        object.__setattr__(self, "_hash", hash(formula))

    @override
    def __setattr__(self, name: str, value: object) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is immutable")

    @override
    def __delattr__(self, name: str) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is immutable")

    @override
    def __reduce__(self) -> tuple[Callable[[_Formula], Self], tuple[_Formula]]:
        return (type(self), (self._formula,))

    @override
    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self) or not isinstance(other, _Symbolic):
            return NotImplemented
        return self is other or (self._hash == other._hash and self._formula == other._formula)

    @override
    def __hash__(self) -> int:
        return self._hash

    def __lt__(self, other: object) -> NoReturn:
        raise TypeError("colors have no order; key by index or role")

    def __le__(self, other: object) -> NoReturn:
        raise TypeError("colors have no order; key by index or role")

    def __gt__(self, other: object) -> NoReturn:
        raise TypeError("colors have no order; key by index or role")

    def __ge__(self, other: object) -> NoReturn:
        raise TypeError("colors have no order; key by index or role")

    @override
    def __str__(self) -> NoReturn:
        raise TypeError(
            f"a {type(self).__name__} has no text form; pass it to a drawing call (got {self!r})"
        )

    @override
    def __format__(self, spec: str) -> NoReturn:
        raise TypeError(
            f"a {type(self).__name__} has no text form; pass it to a drawing call (got {self!r})"
        )

    @override
    def __repr__(self) -> str:
        f = self._formula
        if f[0] == 0:
            return TOKENS[f[1]].upper()
        if f[0] == 1:
            return "MASK_WHITE" if f[1] == 255 else "MASK_BLACK"
        if f[0] == 2:
            return f"mix({f[1]!r}, {f[2]!r}, {f[3]!r})"
        return f"by_regime({f[1]!r}, {f[2]!r})"


@final
class Color(_Symbolic):
    """A theme color: a token, a mix of theme colors, or a per-regime choice.

    Compares and hashes by formula, so mix(a, b, 0.5) == mix(a, b, 0.5) but not
    mix(b, a, 0.5); has no order and no text form (TypeError).
    """

    __slots__ = ()


@final
class MaskColor(_Symbolic):
    """A mask color: MASK_WHITE (shows), MASK_BLACK (hides) or a mix of the two.

    The same semantics as Color; the two never mix.
    """

    __slots__ = ()


_TOKEN: Final[dict[str, Color]] = {name: Color((0, i)) for i, name in enumerate(TOKENS)}

BLACK: Final = _TOKEN["black"]
BG_DEEP: Final = _TOKEN["bg_deep"]
BG: Final = _TOKEN["bg"]
BG_ALT: Final = _TOKEN["bg_alt"]
UI: Final = _TOKEN["ui"]
UI_ALT: Final = _TOKEN["ui_alt"]
UI_HI: Final = _TOKEN["ui_hi"]
MUTED: Final = _TOKEN["muted"]
FG_ALT: Final = _TOKEN["fg_alt"]
FG: Final = _TOKEN["fg"]
ACCENT_HI: Final = _TOKEN["accent_hi"]
ACCENT: Final = _TOKEN["accent"]
ACCENT_1: Final = _TOKEN["accent_1"]
ACCENT_2: Final = _TOKEN["accent_2"]
ACCENT_3: Final = _TOKEN["accent_3"]
ACCENT_4: Final = _TOKEN["accent_4"]
ACCENT_5: Final = _TOKEN["accent_5"]
ACCENT_6: Final = _TOKEN["accent_6"]
ACCENT_7: Final = _TOKEN["accent_7"]
ACCENT_8: Final = _TOKEN["accent_8"]

MASK_WHITE: Final = MaskColor((1, 255))
MASK_BLACK: Final = MaskColor((1, 0))


def token(name: str) -> Color:
    """The token color for any of the 21 names in TOKENS, orange_dark included.

    Raises ValueError for any other name.
    """
    c = _TOKEN.get(name)
    if c is None:
        raise ValueError(f"unknown token {name!r} (known: {', '.join(TOKENS)})")
    return c


def _amount(t: object, what: str) -> float:
    f = real(t, f"{what} t")
    if not 0 <= f <= 1:
        raise ValueError(f"{what} t must be within [0, 1], got {f}")
    return f


def _kind(c: object, what: str) -> type[Color] | type[MaskColor]:
    if isinstance(c, Color):
        return Color
    if isinstance(c, MaskColor):
        return MaskColor
    if isinstance(c, str):
        raise TypeError(f"raw color strings are not colors; use a token or mix() (got {c!r})")
    raise TypeError(f"{what} takes colors, got {c!r}")


@overload
def mix(a: Color, b: Color, t: Num) -> Color: ...
@overload
def mix(a: MaskColor, b: MaskColor, t: Num) -> MaskColor: ...
def mix(a: Color | MaskColor, b: Color | MaskColor, t: Num) -> Color | MaskColor:
    """The linear blend from `a` (t = 0) to `b` (t = 1), rounded per channel when resolved.

    Canonical forms, in this order: t == 0 gives `a`, t == 1 gives `b`, and a == b gives `a`.
    Raises TypeError for a bool or non-numeric `t`, for non-colors and for a Color mixed
    with a MaskColor; ValueError when `t` is outside [0, 1] or NaN.
    """
    f = _amount(t, "mix")
    ka, kb = _kind(a, "mix"), _kind(b, "mix")
    if ka is not kb:
        raise TypeError(f"mix cannot blend a Color with a MaskColor (got {a!r}, {b!r})")
    if f == 0:
        return a
    if f == 1:
        return b
    if a == b:
        return a
    if isinstance(a, Color) and isinstance(b, Color):
        return Color((2, a, b, f))
    if isinstance(a, MaskColor) and isinstance(b, MaskColor):
        return MaskColor((2, a, b, f))
    raise AssertionError("unreachable")


@overload
def ramp(a: Color, b: Color, n: int) -> list[Color]: ...
@overload
def ramp(a: MaskColor, b: MaskColor, n: int) -> list[MaskColor]: ...
def ramp(a: Color | MaskColor, b: Color | MaskColor, n: int) -> list[Color] | list[MaskColor]:
    """`n` colors evenly spaced from `a` to `b`, both included; [a] when n == 1.

    Raises ValueError when n < 1, and what mix raises for the colors.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f"ramp n takes an int, got {n!r}")
    if n < 1:
        raise ValueError(f"ramp takes n >= 1, got {n}")
    if _kind(a, "ramp") is not _kind(b, "ramp"):
        raise TypeError(f"ramp cannot blend a Color with a MaskColor (got {a!r}, {b!r})")
    if isinstance(a, Color) and isinstance(b, Color):
        return [a] if n == 1 else [mix(a, b, i / (n - 1)) for i in range(n)]
    if isinstance(a, MaskColor) and isinstance(b, MaskColor):
        return [a] if n == 1 else [mix(a, b, i / (n - 1)) for i in range(n)]
    raise AssertionError("unreachable")


@final
class Ladder(tuple[Color, ...]):
    """The n rungs ladder() returns: a tuple of colors plus a quantizer over them."""

    __slots__ = ()

    @overload
    def rung(self, v: Num) -> int: ...
    @overload
    def rung(self, v: NDArray[np.floating]) -> NDArray[np.int64]: ...
    def rung(self, v: Num | NDArray[np.floating]) -> int | NDArray[np.int64]:
        """The rung for `v`, clamped to [0, 1], in n equal bins: min(n - 1, int(v * n)).

        Element-wise for arrays. Raises ValueError for NaN, in an array too.
        """
        n = len(self)
        if isinstance(v, np.ndarray):
            f = np.asarray(v, dtype=np.float64)
            if bool(np.isnan(f).any()):
                raise ValueError("rung takes numbers, got NaN in the array")
            return np.minimum(n - 1, (np.clip(f, 0.0, 1.0) * n).astype(np.int64))
        f = real(v, "rung")
        if math.isnan(f):
            raise ValueError("rung takes a number, got NaN")
        return min(n - 1, int(min(max(f, 0.0), 1.0) * n))

    def at(self, v: Num) -> Color:
        """self[self.rung(v)]."""
        return self[self.rung(v)]


def ladder(stops: Sequence[Color], n: int) -> Ladder:
    """`n` rungs spaced evenly along the piecewise-linear path through `stops`.

    With k = len(stops), rung i sits at u = i / (n - 1) * (k - 1) and is
    mix(stops[j], stops[j + 1], u - j) with j = min(k - 2, floor(u)); rung 0 is stops[0] and
    rung n - 1 is stops[-1]. Raises ValueError unless k >= 2 and n >= 2, and TypeError for
    anything but theme colors.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f"ladder n takes an int, got {n!r}")
    cs = tuple(stops)
    for c in cs:
        if not isinstance(c, Color):
            _kind(c, "ladder")
            raise TypeError(f"ladder takes theme colors, got {c!r}")
    k = len(cs)
    if k < 2 or n < 2:
        raise ValueError(f"ladder needs at least 2 stops and n >= 2, got {k} stops and n = {n}")
    rungs: list[Color] = []
    for i in range(n):
        u = i / (n - 1) * (k - 1)
        j = min(k - 2, math.floor(u))
        rungs.append(mix(cs[j], cs[j + 1], u - j))
    return Ladder(rungs)


def by_regime(dark: Color, light: Color) -> Color:
    """A color resolving to `dark` in the dark regime and `light` in the light one.

    by_regime(a, a) is `a`. Raises TypeError for anything but theme colors.
    """
    for c in (dark, light):
        if not isinstance(c, Color):
            _kind(c, "by_regime")
            raise TypeError(f"by_regime takes theme colors, got {c!r}")
    return dark if dark == light else Color((3, dark, light))


def resolve(c: Color | MaskColor, tokens: Mapping[str, str]) -> str:
    """`c` as uppercase #RRGGBB under the 21-token dict `tokens` (from _theme.theme_tokens).

    A mix resolves through _theme.mix, which rounds each channel half to even once per mix;
    by_regime picks by _theme.is_light(tokens["bg"], tokens["fg"]).
    """
    f = c._formula
    if f[0] == 0:
        return tokens[TOKENS[f[1]]].upper()
    if f[0] == 1:
        return "#FFFFFF" if f[1] == 255 else "#000000"
    if f[0] == 2:
        return hex_mix(resolve(f[1], tokens), resolve(f[2], tokens), f[3])
    light = is_light(tokens["bg"], tokens["fg"])
    return resolve(f[2] if light else f[1], tokens)


def coefs(c: Color | MaskColor, light: bool) -> Coefs:
    """`c` in the light (or dark) regime as Coefs (see _theme.Coefs): what resolve() gives
    under any theme of that regime, except for the rounding it applies per token and per mix."""
    f = c._formula
    if f[0] == 0:
        return token_coefs(TOKENS[f[1]], light)
    if f[0] == 1:
        level = float(f[1])
        return (0.0, 0.0, 0.0, level, level, level)
    if f[0] == 2:
        return blend_coefs(coefs(f[1], light), coefs(f[2], light), f[3])
    return coefs(f[2] if light else f[1], light)

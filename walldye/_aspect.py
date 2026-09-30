"""Aspect ratios and canvas sizes.

The short side of every canvas is SHORT pixels; the long side follows the aspect ratio, so
stroke widths read the same on every screen shape.
"""

import math
from collections.abc import Sequence
from typing import Final, Literal

type Aspect = Literal["16:9", "16:10", "21:9", "32:9", "9:19.5", "10:16"]

SHORT: Final = 1080
SITE_ASPECTS: Final[tuple[Aspect, ...]] = ("16:9", "16:10", "21:9", "32:9", "9:19.5", "10:16")


def canvas_size(aspect: str | float = "16:9") -> tuple[int, int]:
    """(w, h) in pixels for an aspect such as '16:9', '9:19.5', '3440x1440' or a w/h ratio.

    The short side is SHORT and the long side is rounded to whole pixels. Raises ValueError
    for anything that is not two positive numbers separated by ':' or 'x', or a positive ratio.
    """
    if isinstance(aspect, str):
        try:
            a, b = (float(v) for v in aspect.lower().replace("x", ":").split(":"))
        except ValueError:
            raise ValueError(
                f"not an aspect: {aspect!r} (want e.g. '16:9' or '3440x1440')"
            ) from None
        ratio = a / b if a > 0 and b > 0 else math.nan
    else:
        ratio = float(aspect)
    if not (math.isfinite(ratio) and ratio > 0):
        raise ValueError(f"not an aspect: {aspect!r}")
    return (round(SHORT * ratio), SHORT) if ratio >= 1 else (SHORT, round(SHORT / ratio))


def _ratio(aspect: str) -> float:
    w, h = canvas_size(aspect)
    return w / h


def supports(declared: Literal["any"] | Sequence[str], aspect: str) -> bool:
    """Whether a design declaring `declared` composes for `aspect`: "any", 16:9, or a declared
    aspect whose ratio is within 1% of it."""
    if declared == "any":
        return True
    want = _ratio(aspect)
    return any(abs(_ratio(a) - want) / want < 0.01 for a in ("16:9", *declared))


def native_aspects(declared: Literal["any"] | Sequence[str]) -> tuple[Aspect, ...]:
    """The SITE_ASPECTS a design declaring `declared` renders natively, in order; always 16:9."""
    return tuple(a for a in SITE_ASPECTS if supports(declared, a))

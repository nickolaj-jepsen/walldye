"""Aspect ratios, canvas sizes and template file names.

The short side of every canvas is SHORT pixels; the long side follows the aspect ratio, so
stroke widths read the same on every screen shape.
"""

import math
import re
from collections.abc import Sequence
from typing import Final, Literal

type Aspect = Literal["16:9", "16:10", "21:9", "32:9", "9:19.5", "10:16"]

SHORT: Final = 1080
SITE_ASPECTS: Final[tuple[Aspect, ...]] = ("16:9", "16:10", "21:9", "32:9", "9:19.5", "10:16")
TEMPLATE_NAME: Final = re.compile(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(\.light)?\.svg")


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
    """The SITE_ASPECTS a design declaring `declared` renders natively, in SITE_ASPECTS order.

    16:9 is always among them.
    """
    return tuple(a for a in SITE_ASPECTS if supports(declared, a))


def aspect_label(aspect: str) -> str:
    """File label of an aspect: '9:19.5' -> '9x19.5'."""
    a, b = aspect.lower().replace("x", ":").split(":")
    return f"{float(a):g}x{float(b):g}"


def template_name(aspect: str, light: bool = False) -> str:
    """Template file name: '16:9' -> '16x9.svg'; '9:19.5' with `light` -> '9x19.5.light.svg'."""
    return f"{aspect_label(aspect)}{'.light' if light else ''}.svg"


def parse_template_name(name: str) -> tuple[str, bool]:
    """(aspect, light) of a template file name: '9x19.5.light.svg' -> ('9:19.5', True).

    Raises ValueError when `name` is not a template name.
    """
    m = TEMPLATE_NAME.fullmatch(name)
    if m is None:
        raise ValueError(f"not a template name: {name!r}")
    return f"{m.group(1)}:{m.group(2)}", m.group(3) is not None

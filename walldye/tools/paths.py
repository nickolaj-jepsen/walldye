"""Where the tools read and write a piece's files."""

import re
from typing import Final

TEMPLATE_NAME: Final = re.compile(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(\.light)?\.svg")


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

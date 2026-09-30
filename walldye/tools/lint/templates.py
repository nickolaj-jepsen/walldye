from walldye._aspect import canvas_size
from walldye.tools import raster

"""Template lints: what an SVG may contain and how large it may be, and pixel grid origins."""

import xml.etree.ElementTree as ET
from collections.abc import Sequence

type Lints = tuple[list[str], list[str]]  # (errors, warnings)

MAX_BYTES, WARN_BYTES = 1_000_000, 600_000


MAX_ELEMENTS, WARN_ELEMENTS = 20_000, 15_000


def svg(text: str) -> Lints:
    """(errors, warnings) for one template: invalid XML, <text>, <filter>, <image>, size and
    element count over MAX_* are errors; over WARN_* warnings."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return [f"invalid XML: {e}"], []
    errors: list[str] = []
    warnings: list[str] = []
    tags = [el.tag.rpartition("}")[2] for el in root.iter()]
    if "text" in tags:
        errors.append("<text> depends on installed fonts; draw glyphs as paths (walldye.pixel)")
    if "filter" in tags:
        errors.append("<filter> is not allowed: slow at 4K, soft, and renderers disagree")
    if "image" in tags:
        errors.append("<image> is not allowed: templates are self-contained vectors")
    size = len(text.encode())
    for value, hard, soft, what in (
        (size, MAX_BYTES, WARN_BYTES, f"{size:,} bytes"),
        (len(tags), MAX_ELEMENTS, WARN_ELEMENTS, f"{len(tags)} elements"),
    ):
        if value > hard:
            errors.append(
                f"{what} is over the limit of {hard:,}; merge shapes into one <path> per color"
            )
        elif value > soft:
            warnings.append(
                f"{what} is heavy (over {soft:,}); merge shapes into one <path> per color"
            )
    return errors, warnings


def pixel_origins(grids: Sequence[tuple[float, float, float]]) -> list[str]:
    """Warnings for pixel grids (cell, x, y) whose origin is not a whole unit."""
    off = sorted({(x, y, cell) for cell, x, y in grids if x % 1 != 0 or y % 1 != 0})
    return [
        f"pixel grid origin ({x:g}, {y:g}) is not a whole unit; snap it to the {cell:g}-unit cell grid"
        for x, y, cell in off
    ]


def viewbox(svg: str, aspect: str) -> list[str]:
    """An error unless the root viewBox of `svg` is the canvas of `aspect`, "0 0 w h"."""
    w, h = canvas_size(aspect)
    got = raster.viewbox(svg)
    return [] if got == f"0 0 {w} {h}" else [f'viewBox must be "0 0 {w} {h}", not {got!r}']

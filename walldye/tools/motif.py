"""A drawn motif's placement: rewriting its group's transform, cutting it out of a template, and
the bounds a placement keeps.

src/lib/__fixtures__/motif.json is the spec; src/lib/motif.ts runs the same fixture.
"""

import math
import re
from typing import Final

from walldye._document import Box, MotifInfo
from walldye._path import fmt

TAG: Final = re.compile(r'<g data-motif="" transform="([^"]*)">')
ROOT: Final = re.compile(r"<svg\b[^>]*>\n")
SIZE_ROUNDING: Final = 5e-5  # a size written to 4 decimals is this close to the one meant

type Place = tuple[float, float, float]  # anchor x, y in canvas units, and size k


def transform(x: float, y: float, k: float) -> str:
    """The motif group's transform for anchor (x, y) and size k: translate(x y), then
    scale(k) unless k is 1; x and y to 2 decimals, k to 4."""
    head = f"translate({fmt(float(x), 2)} {fmt(float(y), 2)})"
    return head if k == 1 else f"{head} scale({fmt(float(k), 4)})"


def place(svg: str, x: float, y: float, k: float) -> str:
    """`svg` with its motif group placed at (x, y), size k. ValueError when it has no motif."""
    m = TAG.search(svg)
    if m is None:
        raise ValueError("the SVG has no motif to place")
    return f'{svg[: m.start()]}<g data-motif="" transform="{transform(x, y, k)}">{svg[m.end() :]}'


def unplaced(svg: str) -> str:
    """`svg` with its motif group's transform emptied, so two placements compare equal; `svg`
    itself when it has no motif."""
    return TAG.sub('<g data-motif="" transform="">', svg, count=1)


def ground(svg: str) -> str:
    """`svg` without its motif group, which is always the root's last child; `svg` itself when
    it has no motif."""
    m = TAG.search(svg)
    return svg if m is None else f"{svg[: m.start()]}</svg>\n"


def alone(svg: str, box: Box) -> str:
    """The motif of `svg` on its own: the root element showing the motif-local `box`, the
    template's <defs>, and the motif group untransformed. ValueError when it has no motif."""
    root, m = ROOT.match(svg), TAG.search(svg)
    if root is None or m is None:
        raise ValueError("the SVG has no motif to cut out")
    defs = re.match(r"<defs>.*?</defs>\n", svg[root.end() :], re.DOTALL)
    x, y, w, h = (fmt(float(v), 2) for v in box)
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}"'
        f' width="{w}" height="{h}">\n'
    )
    body = svg[m.end() : svg.rindex("</svg>")]
    return f'{head}{"" if defs is None else defs.group(0)}<g data-motif="">{body}</svg>\n'


def parse(text: str) -> Place:
    """`X,Y,K` as a placement. ValueError unless it is three finite numbers."""
    error = ValueError(f"a placement is X,Y,K (canvas units and a size), got {text!r}")
    parts = text.split(",")
    if len(parts) != 3:
        raise error
    try:
        x, y, k = (float(p) for p in parts)
    except ValueError:
        raise error from None
    if not all(math.isfinite(v) for v in (x, y, k)):
        raise error
    return x, y, k


def problems(info: MotifInfo, w: int, h: int, where: Place) -> list[str]:
    """Why `where` is not a placement a visitor could make on a w x h canvas: the anchor off
    the canvas, a size outside the motif's scale, or one that leaves its cell fractional."""
    x, y, k = where
    out: list[str] = []
    if not (0 <= x <= w and 0 <= y <= h):
        out.append(f"the anchor ({x:g}, {y:g}) is off the {w}x{h} canvas")
    lo, hi = info.scale
    if not lo <= k <= hi:
        out.append(f"the size {k:g} is outside {lo:g}..{hi:g}")
    cell = info.cell
    if cell is not None and abs(cell * k - round(cell * k)) > cell * SIZE_ROUNDING + 1e-9:
        out.append(f"the size {k:g} makes the {cell:g}-unit cell fractional")
    return out


def size_range(info: MotifInfo) -> tuple[float, float]:
    """The smallest and largest sizes the site offers: the motif's scale, narrowed to sizes that
    keep its cell whole and written to 4 decimals."""
    lo, hi = info.scale
    if info.cell is None:
        return lo, hi
    c = info.cell
    return round(math.ceil(lo * c - 1e-9) / c, 4), round(math.floor(hi * c + 1e-9) / c, 4)


def as_json(info: MotifInfo) -> dict[str, object]:
    """`info` as slots.json stores it in each template entry."""
    return {
        "at": [round(v, 2) for v in info.at],
        "extent": [round(v, 2) for v in info.extent],
        "handle": [round(v, 2) for v in info.handle],
        "overscan": info.overscan,
        "cell": info.cell,
        "scale": list(info.scale),
    }

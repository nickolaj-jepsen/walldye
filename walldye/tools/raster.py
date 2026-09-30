"""Rasterizing, cropping and measuring rendered SVG: the background, the ink and its focus."""

import io
import re
from collections.abc import Sequence
from typing import Final

import numpy as np
import resvg_py
from numpy.typing import NDArray
from PIL import Image

from walldye._aspect import canvas_size
from walldye._theme import FIREPROOF, hex_to_rgb
from walldye.tools import loader

FIREPROOF_BG: Final = FIREPROOF["bg"]


FOCUS_WIDTH: Final = 480  # px wide the focus is measured at


type Crop = tuple[float, float, float, float]


_BACKGROUND: Final = re.compile(
    r"<svg\b[^\n]*\n(?:<defs>[^\n]*</defs>\n)?"
    r'<rect x="0" y="0" width="\d+" height="\d+" fill="(#[0-9A-Fa-f]{6})"/>\n'
)


def viewbox(svg: str) -> str | None:
    """The root <svg> element's viewBox value, or None when it has none."""
    root = re.search(r"<svg\b[^>]*>", svg)
    m = None if root is None else re.search(r'\sviewBox\s*=\s*"([^"]*)"', root.group(0))
    return None if m is None else m.group(1)


def crop_svg(svg: str, crop: Crop) -> str:
    """`svg` cut to the canvas box `crop` (x, y, w, h): the root viewBox becomes the box,
    width/height its size."""
    x, y, w, h = crop
    svg = re.sub(r'viewBox="[^"]*"', f'viewBox="{x:g} {y:g} {w:g} {h:g}"', svg, count=1)
    return _sized(svg, w, h)


def _sized(svg: str, w: float, h: float) -> str:
    return re.sub(
        r'(<svg[^>]*?) width="[^"]*" height="[^"]*"',
        lambda m: f'{m.group(1)} width="{w:g}" height="{h:g}"',
        svg,
        count=1,
    )


def _crop_span(aspect: str) -> tuple[bool, float]:
    """(whether `aspect` is narrower than 16:9, the crop's size along its moving axis)."""
    cw, ch = canvas_size("16:9")
    aw, ah = canvas_size(aspect)
    ratio = aw / ah
    narrow = ratio < cw / ch
    return narrow, ch * ratio if narrow else cw / ratio


def crop_position(aspect: str, focus: tuple[float, float]) -> float:
    """Where along its moving axis the crop of the 16:9 canvas to `aspect` sits when centered
    on `focus` (fractions of the canvas): 0 at the left or top edge, 1 at the other, clamped
    and rounded to 0.001, as the site's crop slider holds it."""
    cw, ch = canvas_size("16:9")
    narrow, size = _crop_span(aspect)
    span = size / (cw if narrow else ch)
    f = focus[0] if narrow else focus[1]
    return 0.5 if span >= 1 else round(min(1.0, max(0.0, (f - span / 2) / (1 - span))), 3)


def fit_crop(aspect: str, focus: tuple[float, float]) -> Crop:
    """The box of the 16:9 canvas an `aspect` it wasn't drawn for is cut from, as the site
    cuts it: the canvas's full height for a narrower aspect, else its full width, slid along
    the other axis to crop_position()."""
    cw, ch = canvas_size("16:9")
    narrow, size = _crop_span(aspect)
    t = crop_position(aspect, focus)
    if narrow:
        return t * (cw - size), 0.0, size, float(ch)
    return 0.0, t * (ch - size), float(cw), size


def template_focus(
    slug: str, variant: str = "default", overrides: Sequence[str] = ()
) -> tuple[float, float]:
    """focus() of the piece's 16:9 dark template, the one build stores in slots.json."""
    svg = loader.render(slug, "fireproof", "16:9", variant, overrides)
    return focus(rasterize(svg, FOCUS_WIDTH), background(svg))


def rasterize(svg: str, width: int, crop: Crop | None = None) -> Image.Image:
    """RGB image of `svg`, `width` px wide; the height follows the viewBox (or `crop`) aspect.

    `crop` is applied with crop_svg(). resvg's ValueError on invalid SVG propagates.
    """
    if crop is not None:
        svg = crop_svg(svg, crop)
        _, _, w, h = crop
    else:
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        w, h = (16.0, 9.0) if m is None else (float(m.group(1)), float(m.group(2)))
    height = round(width * h / w)
    # resvg keeps the root's width:height, and rounding that can cost a pixel of the target.
    svg = _sized(svg, width, height)
    data = resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height)
    # resvg emits RGBA; wallpapers are opaque, and some setters dislike alpha.
    return Image.open(io.BytesIO(data)).convert("RGB")


def background(svg: str) -> str:
    """The fill of a template's background rect, the first element after its <defs> line: what
    its ink map and focus are measured from. FIREPROOF_BG for a template laid out otherwise (a
    legacy piece's source.svg)."""
    m = _BACKGROUND.match(svg)
    return FIREPROOF_BG if m is None else m.group(1)


def _ink(img: Image.Image, bg: str) -> NDArray[np.float64]:
    pixels = np.asarray(img, dtype=np.float64)
    return np.linalg.norm(pixels - np.array(hex_to_rgb(bg), dtype=np.float64), axis=2)


def ink_map(img: Image.Image, bg: str, size: tuple[int, int] = (64, 36)) -> NDArray[np.float64]:
    """Per-pixel RGB distance from `bg` at `size`, flattened to a unit vector (all zeros when
    blank): what a design 'looks like'. The dot product of two maps is their cosine similarity."""
    d = _ink(img.resize(size), bg)
    n = float(np.linalg.norm(d))
    return d.ravel() / n if n > 0 else d.ravel()


def focus(img: Image.Image, bg: str) -> tuple[float, float]:
    """Ink-weighted centroid of `img` (weights = RGB distance from `bg`) as (x, y) fractions of
    its width and height, rounded to 4 dp; (0.5, 0.5) when nothing differs from `bg`."""
    d = _ink(img, bg)
    total = float(d.sum())
    if total == 0:
        return 0.5, 0.5
    h, w = int(d.shape[0]), int(d.shape[1])
    cols: NDArray[np.float64] = d.sum(axis=0)
    rows: NDArray[np.float64] = d.sum(axis=1)
    fx = float(np.dot(cols, np.arange(w, dtype=np.float64) + 0.5)) / total / w
    fy = float(np.dot(rows, np.arange(h, dtype=np.float64) + 0.5)) / total / h
    return round(fx, 4), round(fy, 4)

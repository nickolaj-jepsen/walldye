"""`walldye preview`: render one piece to a PNG in $WALLDYE_PREVIEW and print fast lint hints."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

import walldye
from walldye import _theme
from walldye.tools import common
from walldye.tools.common import Crop

HINT_TOL = 8.0  # palette_distance (RGB units) past which a colour reads as hardcoded


def preview_dir() -> Path:
    """$WALLDYE_PREVIEW, else <tmp>/walldye."""
    return Path(os.environ.get("WALLDYE_PREVIEW") or Path(tempfile.gettempdir()) / "walldye")


def parse_crop(value: str) -> Crop:
    """`X,Y,W,H` in canvas units; ValueError unless four numbers with W and H positive."""
    try:
        crop = tuple(float(v) for v in value.split(","))
    except ValueError:
        crop = ()
    if len(crop) != 4 or crop[2] <= 0 or crop[3] <= 0:
        raise ValueError(f"bad crop {value!r} (want X,Y,W,H in canvas units, W and H > 0)")
    return crop


def palette_hints(svg: str) -> list[str]:
    """A hint naming the paint colours of `svg` further than HINT_TOL from the current theme's
    token hull (probably hardcoded; a fast stand-in for check's constant-slot rule), or []."""
    from walldye.tools.tokenize import find_colours

    off = sorted(((walldye.palette_distance(c), c) for c in {c for _, _, c in find_colours(svg)}), reverse=True)
    off = [(d, c) for d, c in off if d > HINT_TOL]
    if not off:
        return []
    worst = ", ".join(f"{c} (Δ{d:.0f})" for d, c in off[:6])
    return [f"{len(off)} colour(s) off the theme, hardcoded unless inside a mask: {worst}"]


def lint(
    slug: str, svg: str, aspect: str, grids: list[tuple[float, float, float]]
) -> tuple[list[str], list[str], list[str]]:
    """(errors, warnings, hints) for one render of `slug` at `aspect`, made under the current theme.

    The per-render part of `walldye check` (viewBox; lint.svg limits; lint.source for
    design.py; colour words in the meta.yaml copy; lint.pixel_origins of `grids`, the
    walldye.pixel_grids() of this render) plus palette_hints. Call it before rendering
    anything else: the hint reads the current theme.
    """
    from walldye.tools import lint

    errors, warnings = lint.svg(svg)
    w, h = walldye.canvas_size(aspect)
    if common.viewbox(svg) != f"0 0 {w} {h}":
        errors.append(f'viewBox is not "0 0 {w} {h}"')
    if not common.is_legacy(slug):
        source_errors, source_warnings = lint.source(common.piece_dir(slug) / "design.py")
        errors, warnings = errors + source_errors, warnings + source_warnings
    if (common.piece_dir(slug) / "meta.yaml").exists():
        warnings = warnings + lint.copy_words(common.load_meta(slug))
    return errors, warnings + lint.pixel_origins(grids), palette_hints(svg)


def _light_geometry(slug: str, aspect: str, svg: str, token: str) -> str:
    from walldye.tools.tokenize import skeleton

    if common.load_meta(slug).get("themes") == ["dark"]:
        return "n/a (themes: [dark])"
    dark = svg if token == "fireproof" else common.render(slug, "fireproof", aspect)
    light = svg if token == "flexoki-light" else common.render(slug, "flexoki-light", aspect)
    if skeleton(dark) == skeleton(light):
        return "same as dark (one template serves both regimes)"
    return "differs from dark (build writes a light template for each native aspect)"


def _inkscape(svg: str, width: int, crop: Crop | None) -> Image.Image:
    if not shutil.which("inkscape"):
        sys.exit("inkscape not found on PATH (drop --renderer inkscape to use resvg)")
    with tempfile.TemporaryDirectory() as d:
        src, png = Path(d, "in.svg"), Path(d, "out.png")
        src.write_text(common.crop_svg(svg, crop) if crop else svg)
        subprocess.run(["inkscape", "-w", str(width), str(src), "-o", str(png)], check=True, capture_output=True)
        return Image.open(png).convert("RGB")


def run(slug: str, seeds: dict[str, str], aspect: str, crop: Crop | None, width: int, renderer: str) -> int:
    """Render `slug` under `seeds` at `aspect` and write `<slug>-<token>-<aspect>[-crop-X-Y-W-H].png`
    to preview_dir(), `width` px on its long side (of `crop`, when given). Prints lint lines, the
    regime, whether light geometry differs, then the PNG path last. Design errors propagate;
    an unreadable ASPECTS exits with its message."""
    token = walldye.theme_token(seeds)
    try:
        declared = common.design_aspects(slug)
    except ValueError as e:
        sys.exit(str(e))
    svg = common.render(slug, seeds, aspect)
    errors, warnings, hints = lint(slug, svg, aspect, walldye.pixel_grids())
    if not walldye.supports(declared, aspect):
        warnings.insert(0, f"{slug} declares ASPECTS={declared}; rendered {aspect} anyway")

    _, _, bw, bh = crop or (0, 0, *walldye.canvas_size(aspect))
    px = width if bw >= bh else round(width * bw / bh)
    img = _inkscape(svg, px, crop) if renderer == "inkscape" else common.rasterise(svg, px, crop)
    name = f"{slug}-{token}-{walldye.aspect_label(aspect)}"
    if crop:
        name += "-crop-" + "-".join(f"{v:g}" for v in crop)
    png = preview_dir() / f"{name}.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    img.save(png, optimize=True)

    for label, lines in (("error", errors), ("warning", warnings), ("hint", hints)):
        for line in lines:
            print(f"{label}: {line}")
    print("lint: ok" if not (errors or warnings) else f"lint: {len(errors)} error(s), {len(warnings)} warning(s)")
    regime = "light" if _theme.is_light(seeds["bg"], seeds["fg"]) else "dark"
    print(f"regime: {regime} ({token})")
    print(f"light geometry: {_light_geometry(slug, aspect, svg, token)}")
    print(png)
    return 0

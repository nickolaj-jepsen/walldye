"""`walldye preview`: draw one piece to a PNG in $WALLDYE_PREVIEW and print the fast lints."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from walldye._aspect import canvas_size, supports
from walldye._design import RenderSpec
from walldye.tools import lint as lints
from walldye.tools import loader, metadata, paths, raster, themes
from walldye.tools.errors import UsageError
from walldye.tools.paths import aspect_label
from walldye.tools.raster import Crop
from walldye.tools.themes import theme_token


def preview_dir() -> Path:
    """$WALLDYE_PREVIEW, else <tmp>/walldye."""
    env = os.environ.get("WALLDYE_PREVIEW")
    return Path(env) if env is not None and env != "" else Path(tempfile.gettempdir()) / "walldye"


def parse_crop(value: str) -> Crop:
    """`X,Y,W,H` in canvas units; ValueError unless four numbers with W and H positive."""
    try:
        x, y, w, h = (float(v) for v in value.split(","))
    except ValueError:
        raise ValueError(
            f"bad crop {value!r} (want X,Y,W,H in canvas units, W and H > 0)"
        ) from None
    if w <= 0 or h <= 0:
        raise ValueError(f"bad crop {value!r} (want X,Y,W,H in canvas units, W and H > 0)")
    return x, y, w, h


def lint(
    slug: str, svg: str, aspect: str, grids: Sequence[tuple[float, float, float]]
) -> tuple[list[str], list[str]]:
    """(errors, warnings) for one render of `slug` at `aspect`: the per-render part of
    `walldye check` (viewBox, the template limits, the design lint, color words in the
    meta.yaml copy, whole-unit origins of `grids`, the document's pixel grids)."""
    errors, warnings = lints.svg(svg)
    w, h = canvas_size(aspect)
    if raster.viewbox(svg) != f"0 0 {w} {h}":
        errors.append(f'viewBox is not "0 0 {w} {h}"')
    design = paths.piece_dir(slug) / "design.py"
    if design.exists():
        source_errors, source_warnings = lints.design(design)
        errors, warnings = errors + source_errors, warnings + source_warnings
    if (paths.piece_dir(slug) / "meta.yaml").exists():
        warnings = warnings + lints.copy_words(metadata.load_meta(slug))
    return errors, warnings + lints.pixel_origins(grids)


def file_name(slug: str, variant: str, token: str, aspect: str, overrides: Sequence[str]) -> str:
    """`<slug>[--<variant>]-<token>-<aspect>[-set-<k>-<v>...]`: the variant only when named,
    one -set part per override in key order."""
    name = slug if variant == "default" else f"{slug}--{variant}"
    sets = "".join(
        f"-set-{k}-{re.sub(r'[^A-Za-z0-9.]+', '_', v)}"
        for k, _, v in sorted(o.partition("=") for o in overrides)
    )
    return f"{name}-{token}-{aspect_label(aspect)}{sets}"


def _light_geometry(slug: str, spec: RenderSpec) -> str:
    piece = loader.load(slug)
    dark, light = (
        loader.draw(piece, RenderSpec(spec.variant, spec.params, spec.aspect, r))
        for r in ("dark", "light")
    )
    if dark.skeleton() == light.skeleton():
        return "same as dark (one template serves both regimes)"
    return "differs from dark (build writes a light template for each native aspect)"


def _inkscape(svg: str, width: int, crop: Crop | None) -> Image.Image:
    if shutil.which("inkscape") is None:
        sys.exit("inkscape not found on PATH (drop --renderer inkscape to use resvg)")
    with tempfile.TemporaryDirectory() as d:
        src, png = Path(d, "in.svg"), Path(d, "out.png")
        src.write_text(raster.crop_svg(svg, crop) if crop is not None else svg)
        subprocess.run(
            ["inkscape", "-w", str(width), str(src), "-o", str(png)],
            check=True,
            capture_output=True,
        )
        return Image.open(png).convert("RGB")


def run(
    slug: str,
    seeds: dict[str, str],
    aspect: str,
    crop: Crop | None,
    width: int,
    renderer: str,
    variant: str = "default",
    overrides: Sequence[str] = (),
) -> int:
    """Draw `variant` of `slug` (with the `--set` `overrides`) for the regime of `seeds` at
    `aspect` and write file_name(...)[-crop-X-Y-W-H].png to preview_dir(), `width` px on its
    long side (of `crop`, when given). Prints lint lines, the regime, whether light geometry
    differs, then the PNG path last; soft-range warnings go to stderr. UsageError for an
    undeclared variant or a bad override; design errors propagate."""
    piece = loader.load(slug)
    loader.variant_of(piece, slug, variant)
    try:
        params, set_warnings = loader.params_for(piece, variant, overrides)
    except (ValueError, TypeError) as e:
        raise UsageError(str(e)) from None
    for w in set_warnings:
        print(f"warning: {w}", file=sys.stderr)
    token = theme_token(seeds)
    spec = RenderSpec(variant, params, aspect, themes.regime_of(seeds))
    doc = loader.draw(piece, spec)
    svg = doc.to_svg(themes.tokens_of(seeds))
    errors, warnings = lint(slug, svg, aspect, doc.pixel_grids)
    if not supports(piece.declared_aspects, aspect):
        declared = piece.declared_aspects
        warnings.insert(0, f"{slug} declares aspects={declared!r}; rendered {aspect} anyway")

    _, _, bw, bh = crop if crop is not None else (0.0, 0.0, *map(float, canvas_size(aspect)))
    px = width if bw >= bh else round(width * bw / bh)
    img = _inkscape(svg, px, crop) if renderer == "inkscape" else raster.rasterize(svg, px, crop)
    name = file_name(slug, variant, token, aspect, overrides)
    if crop is not None:
        name += "-crop-" + "-".join(f"{v:g}" for v in crop)
    png = preview_dir() / f"{name}.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    img.save(png, optimize=True)

    for label, lines in (("error", errors), ("warning", warnings)):
        for line in lines:
            print(f"{label}: {line}")
    counts = f"lint: {len(errors)} error(s), {len(warnings)} warning(s)"
    print("lint: ok" if len(errors) + len(warnings) == 0 else counts)
    print(f"regime: {spec.regime} ({token})")
    print(f"light geometry: {_light_geometry(slug, spec)}")
    print(png)
    return 0

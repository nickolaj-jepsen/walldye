"""walldye render: one version of a piece under a theme, as SVG or PNG, at any aspect."""

import sys
from collections.abc import Sequence
from pathlib import Path

from walldye._aspect import canvas_size, supports
from walldye._design import RenderSpec
from walldye.tools import loader, paths, raster, themes
from walldye.tools.errors import UsageError
from walldye.tools.paths import aspect_label
from walldye.tools.themes import theme_token


def run(
    slug: str,
    seeds: dict[str, str],
    *,
    aspect: str = "16:9",
    variant: str = "default",
    crop: raster.Crop | None = None,
    fit: bool = False,
    overrides: Sequence[str] = (),
    output: str | None = None,
    width: int | None = None,
) -> int:
    """`walldye render`: draw `variant` of `slug` under `seeds` at `aspect` and write it to
    `output` (an SVG, a PNG `width` px wide, or "-" for stdout; default
    <slug>[--variant]-<theme>-<aspect>[-crop].svg), cut to `crop` when given. An aspect the
    design does not declare needs `fit`, which cuts it from 16:9 around the focus. UsageError
    for an undeclared aspect without `fit`, `fit` with a crop, a bad override or a width
    without a PNG; exits without writing into a build/ folder."""
    piece = loader.load(slug)
    loader.variant_of(piece, slug, variant)
    native = supports(piece.declared_aspects, aspect)
    fit = fit and not native
    if not native and not fit:
        raise UsageError(
            f"{slug} declares aspects={piece.declared_aspects!r}, not {aspect};"
            " pass --fit, or render 16:9 with --crop"
        )
    if fit and crop is not None:
        raise UsageError(f"--fit picks the crop for {aspect} itself; drop --crop")
    try:
        params, warnings = loader.params_for(piece, variant, overrides)
    except (ValueError, TypeError) as e:
        raise UsageError(str(e)) from None
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    drawn = "16:9" if fit else aspect
    doc = loader.draw(piece, RenderSpec(variant, params, drawn, themes.regime_of(seeds)))
    svg = doc.to_svg(themes.tokens_of(seeds))
    if fit:
        focus = raster.template_focus(slug, variant, overrides)
        crop = raster.fit_crop(aspect, focus)
    drawn_svg = svg
    if crop is not None:
        svg = raster.crop_svg(svg, crop)
    png = output is not None and output.lower().endswith(".png")
    if width is not None and not png:
        raise UsageError("--width sizes a PNG; name one with -o PATH.png")
    if output == "-":
        sys.stdout.write(svg)
        return 0
    name = slug if variant == "default" else f"{slug}--{variant}"
    tail = "-crop" if crop is not None else ""
    default = f"{name}-{theme_token(seeds)}-{aspect_label(aspect)}{tail}.svg"
    out = Path(output if output is not None else default)
    wallpapers, target = paths.WALLPAPERS.resolve(), out.resolve()
    if target.is_relative_to(wallpapers) and "build" in target.relative_to(wallpapers).parts[1:2]:
        sys.exit(f"refusing to write {out}: only walldye build writes into build/")
    out.parent.mkdir(parents=True, exist_ok=True)
    if png:
        cw, ch = canvas_size(drawn)
        box = crop if crop is not None else (0.0, 0.0, float(cw), float(ch))
        px = width if width is not None else round(box[2])
        raster.rasterize(drawn_svg, px, box).save(out)
    else:
        out.write_text(svg)
    print(out)
    return 0

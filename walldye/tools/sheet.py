"""`walldye sheet`: a contact-sheet PNG of built templates, or of one design drawn afresh
for every combination of `--wedge` values and `--seeds`."""

import itertools
import math
import sys
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from walldye._design import RenderSpec
from walldye.tools import knobs, loader, metadata, paths, raster, themes
from walldye.tools.errors import UsageError
from walldye.tools.paths import aspect_label
from walldye.tools.preview import preview_dir
from walldye.tools.themes import theme_token

PAD, LABEL = 8, 22


def themed(slug: str, seeds: dict[str, str], variant: str = "default", aspect: str = "16:9") -> str:
    """A variant's built template at `aspect` recolored to `seeds` the way the site does
    it: build.select picks the slots.json entry and build.recolor applies it; fireproof's
    exact seeds return the dark template untouched. KeyError if slots.json lacks the entry,
    FileNotFoundError when not built."""
    from walldye.tools.build import entries, load_slots, recolor, select

    slots = load_slots(slug, variant)
    if slots is None:
        raise FileNotFoundError(f"{paths.build_dir(slug, variant)} has no slots.json")
    table = entries(slots)
    d = paths.build_dir(slug, variant)
    if theme_token(seeds) == "fireproof":
        return (d / table[f"{aspect}/dark"]["file"]).read_text()
    k = select(slots, aspect, seeds)
    return recolor((d / table[k]["file"]).read_text(), table[k], seeds)


def _grid(cells: Sequence[tuple[str, Image.Image]], cols: int, thumb: int) -> Image.Image:
    th = max(im.height for _, im in cells)
    cols = min(cols, len(cells))
    rows = -(-len(cells) // cols)
    size = (cols * (thumb + PAD) + PAD, rows * (th + PAD + LABEL) + PAD)
    sheet = Image.new("RGB", size, "black")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=14)
    for k, (label, im) in enumerate(cells):
        x, y = PAD + (k % cols) * (thumb + PAD), PAD + (k // cols) * (th + PAD + LABEL)
        sheet.paste(im, (x, y))
        draw.text((x + 4, y + im.height + 3), label, fill="#DAD8CE", font=font)
    return sheet


def _save(sheet: Image.Image, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print(path)
    return 0


def run(
    slugs: Sequence[str],
    seeds: dict[str, str],
    cols: int | None,
    thumb: int,
    out: str | None,
    variant: str = "default",
    aspect: str = "16:9",
) -> int:
    """Write a sheet of the built `variant` templates of `slugs` at `aspect` (thumbnails
    `thumb` px wide, `cols` per row, default 4, slug labels) under `seeds` to `out`, default
    preview_dir()/sheet-<token>.png, and print its path. Pieces without that variant's
    build, or without a template at `aspect`, are skipped with a note; exits if none is left."""
    thumbs: list[tuple[str, Image.Image]] = []
    for slug in slugs:
        try:
            svg = themed(slug, seeds, variant, aspect)
        except FileNotFoundError:
            if variant != "default" and variant not in _declared(slug):
                print(f"skip {slug}: no variant {variant}", file=sys.stderr)
                continue
            where = "" if variant == "default" else f" --variant {variant}"
            print(f"skip {slug}: not built (run walldye build {slug}{where})", file=sys.stderr)
            continue
        except KeyError:
            print(f"skip {slug}: no {aspect} template", file=sys.stderr)
            continue
        thumbs.append((slug, raster.rasterize(svg, thumb)))
    if len(thumbs) == 0:
        sys.exit("nothing to put on a sheet")
    name = f"sheet-{theme_token(seeds)}.png"
    return _save(
        _grid(thumbs, 4 if cols is None else cols, thumb),
        Path(out) if out is not None else preview_dir() / name,
    )


def _declared(slug: str) -> dict[str, dict[str, object]]:
    """The versions meta.yaml lists for `slug` (check keeps them equal to design.py's), {} when
    it lists none or cannot be read."""
    try:
        return metadata.meta_variants(metadata.load_meta(slug))
    except (OSError, ValueError):
        return {}


def _label(value: knobs.Value) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def run_fresh(
    slug: str,
    seeds: dict[str, str],
    cols: int | None,
    thumb: int,
    out: str | None,
    variant: str = "default",
    aspect: str = "16:9",
    overrides: Sequence[str] = (),
    wedges: Sequence[str] = (),
    seed_range: str | None = None,
) -> int:
    """Draw `variant` of `slug` afresh (with the `--set` `overrides`) for every combination of
    the `wedges` (`k=SPEC`, varied in order, the first slowest) and the seeds of `seed_range`
    (fastest), under `seeds` at `aspect`, and write a labeled sheet to `out`, default
    preview_dir()/sheet-<slug>[--<variant>]-<token>-<aspect>.png. `cols` defaults to the
    number of values of the fastest axis. Values outside a soft range warn on stderr.
    UsageError for an undeclared variant, a bad spec or value, or more than MAX_CELLS cells."""
    piece = loader.load(slug)
    loader.variant_of(piece, slug, variant)
    try:
        base, warnings = loader.params_for(piece, variant, overrides)
        axes: list[tuple[str, list[knobs.Value]]] = []
        for item in wedges:
            k, sep, spec = item.partition("=")
            if sep == "":
                raise ValueError(f"--wedge takes k=SPEC, got {item!r}")
            info = knobs.knob(piece.params_type, k)
            values = knobs.wedge(info, spec)
            warnings += [w for v in values if (w := knobs.outside(info, v)) is not None]
            axes.append((k, values))
        if seed_range is not None:
            axes.append(("seed", list[knobs.Value](knobs.seeds(seed_range))))
    except ValueError as e:
        raise UsageError(str(e)) from None
    names = [k for k, _ in axes]
    if len(set(names)) != len(names):
        raise UsageError(f"each param varies once, got {', '.join(names)}")
    n = math.prod(len(v) for _, v in axes)
    if n > knobs.MAX_CELLS:
        raise UsageError(f"{n} cells is over the limit of {knobs.MAX_CELLS}")
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    regime, tokens = themes.regime_of(seeds), themes.tokens_of(seeds)
    cells: list[tuple[str, Image.Image]] = []
    for combo in itertools.product(*(v for _, v in axes)):
        try:
            params = knobs.replace(base, dict(zip(names, combo, strict=True)))
        except (TypeError, ValueError) as e:
            raise UsageError(str(e)) from None
        svg = loader.draw(piece, RenderSpec(variant, params, aspect, regime)).to_svg(tokens)
        label = " ".join(f"{k}={_label(v)}" for k, v in zip(names, combo, strict=True))
        cells.append((label if label != "" else slug, raster.rasterize(svg, thumb)))
    per_row = cols if cols is not None else len(axes[-1][1]) if len(axes) > 0 else 1
    name = slug if variant == "default" else f"{slug}--{variant}"
    default = preview_dir() / f"sheet-{name}-{theme_token(seeds)}-{aspect_label(aspect)}.png"
    return _save(_grid(cells, per_row, thumb), Path(out) if out is not None else default)

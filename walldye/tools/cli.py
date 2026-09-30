"""walldye: scaffold, preview, check, build, render, review and sheet the wallpapers in
wallpapers/<slug>/.

Commands that take slugs need them named (or --all); only `themes` covers everything by
default, and `review` defaults to the drafts. --theme takes a preset name or
bg-fg-accent hex seeds (also bg,fg,accent and bg=..,fg=..,accent=..). --variant names a
version declared in design.py (`default` is the unnamed one); --set k=v overrides one param
while exploring.
"""

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from walldye._aspect import aspect_label, canvas_size, supports
from walldye._theme import DEFAULT_THEME, parse_seeds, theme_token
from walldye.tools import common, listing, new, preview, review, sheet

COMMANDS = "new,preview,render,check,build,review,sheet,params,list,drop,themes"
SET_REFUSED = "--set is for exploring; give the values a named variant in design.py"

type Command = Callable[[argparse.Namespace], int]


def _seeds(value: str) -> dict[str, str]:
    try:
        return parse_seeds(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e


def _slug(value: str) -> str:
    try:
        d = common.piece_dir(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e
    if not d.is_dir():
        raise argparse.ArgumentTypeError(f"no {d}")
    return value


def _aspect(value: str) -> str:
    if not common.is_aspect(value):
        raise argparse.ArgumentTypeError(f"bad aspect {value!r} (e.g. 16:9, 9:19.5, 3440x1440)")
    return value


def _positive(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        n = 0
    if n < 1:
        raise argparse.ArgumentTypeError(f"want a positive whole number, not {value!r}")
    return n


def _crop(value: str) -> common.Crop:
    try:
        return preview.parse_crop(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e


def _str(a: argparse.Namespace, name: str) -> str:
    return cast("str", getattr(a, name))


def _opt[T](a: argparse.Namespace, name: str, kind: type[T]) -> T | None:
    value: object = getattr(a, name)
    return value if isinstance(value, kind) else None


def _items(a: argparse.Namespace, name: str) -> list[str]:
    items = cast("list[str] | None", getattr(a, name))
    return [] if items is None else items


def _cmd_new(a: argparse.Namespace) -> int:
    return new.run(_str(a, "slug"), _str(a, "model"))


def _cmd_preview(a: argparse.Namespace) -> int:
    return preview.run(
        _str(a, "slug"),
        cast("dict[str, str]", a.theme),
        _str(a, "aspect"),
        cast("common.Crop | None", a.crop),
        cast("int", a.width),
        _str(a, "renderer"),
        _str(a, "variant"),
        _items(a, "set"),
    )


def _cmd_render(a: argparse.Namespace) -> int:
    slug, aspect, variant = _str(a, "slug"), _str(a, "aspect"), _str(a, "variant")
    seeds = cast("dict[str, str]", a.theme)
    crop = cast("common.Crop | None", a.crop)
    piece = common.load(slug)
    common.variant_of(piece, slug, variant)
    native = supports(piece.declared_aspects, aspect)
    fit = cast("bool", a.fit) and not native
    if not native and not fit:
        raise common.UsageError(
            f"{slug} declares aspects={piece.declared_aspects!r}, not {aspect};"
            " pass --fit, or render 16:9 with --crop"
        )
    if fit and crop is not None:
        raise common.UsageError(f"--fit picks the crop for {aspect} itself; drop --crop")
    overrides = _items(a, "set")
    try:
        params, warnings = common.params_for(piece, variant, overrides)
    except (ValueError, TypeError) as e:
        raise common.UsageError(str(e)) from None
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    from walldye._design import RenderSpec

    drawn = "16:9" if fit else aspect
    doc = common.draw(piece, RenderSpec(variant, params, drawn, common.regime_of(seeds)))
    svg = doc.to_svg(common.tokens_of(seeds))
    if fit:
        focus = common.template_focus(slug, variant, overrides)
        crop = common.fit_crop(aspect, focus)
    drawn_svg = svg
    if crop is not None:
        svg = common.crop_svg(svg, crop)
    output = _opt(a, "output", str)
    width = _opt(a, "width", int)
    png = output is not None and output.lower().endswith(".png")
    if width is not None and not png:
        raise common.UsageError("--width sizes a PNG; name one with -o PATH.png")
    if output == "-":
        sys.stdout.write(svg)
        return 0
    name = slug if variant == "default" else f"{slug}--{variant}"
    tail = "-crop" if crop is not None else ""
    default = f"{name}-{theme_token(seeds)}-{aspect_label(aspect)}{tail}.svg"
    out = Path(output if output is not None else default)
    wallpapers, target = common.WALLPAPERS.resolve(), out.resolve()
    if target.is_relative_to(wallpapers) and "build" in target.relative_to(wallpapers).parts[1:2]:
        sys.exit(f"refusing to write {out}: only walldye build writes into build/")
    out.parent.mkdir(parents=True, exist_ok=True)
    if png:
        cw, ch = canvas_size(drawn)
        box = crop if crop is not None else (0.0, 0.0, float(cw), float(ch))
        px = width if width is not None else round(box[2])
        common.rasterize(drawn_svg, px, box).save(out)
    else:
        out.write_text(svg)
    print(out)
    return 0


def _cmd_check(a: argparse.Namespace) -> int:
    from walldye.tools import check

    return check.run(
        _items(a, "slugs"),
        all=cast("bool", a.all),
        variant=_opt(a, "variant", str),
        paranoid=cast("bool", a.paranoid),
        similar=cast("bool", a.similar),
        jobs=_opt(a, "jobs", int),
    )


def _cmd_build(a: argparse.Namespace) -> int:
    from walldye.tools import build

    return build.run(
        _items(a, "slugs"),
        all=cast("bool", a.all),
        force=cast("bool", a.force),
        variant=_opt(a, "variant", str),
        published=cast("bool", a.published),
        jobs=_opt(a, "jobs", int),
    )


def _cmd_review(a: argparse.Namespace) -> int:
    slugs, everything = _items(a, "slugs"), cast("bool", a.all)
    if everything and len(slugs) > 0:
        raise common.UsageError("review takes slugs or --all, not both")
    timeout, port = cast("float", a.timeout), cast("int", a.port)
    return review.run(slugs, timeout, port, not a.no_open, everything)


def _cmd_sheet(a: argparse.Namespace) -> int:
    seeds = cast("dict[str, str]", a.theme)
    slugs = common.slugs() if a.all else _items(a, "slugs")
    cols, thumb, out = _opt(a, "cols", int), cast("int", a.thumb), _opt(a, "output", str)
    variant, aspect = _str(a, "variant"), _str(a, "aspect")
    wedges, overrides, seeds_range = _items(a, "wedge"), _items(a, "set"), _opt(a, "seeds", str)
    if len(wedges) == 0 and len(overrides) == 0 and seeds_range is None:
        return sheet.run(slugs, seeds, cols, thumb, out, variant, aspect)
    if len(slugs) != 1:
        raise common.UsageError("--wedge, --seeds and --set draw one slug afresh; name one")
    return sheet.run_fresh(
        slugs[0], seeds, cols, thumb, out, variant, aspect, overrides, wedges, seeds_range
    )


def _cmd_params(a: argparse.Namespace) -> int:
    return listing.run_params(_str(a, "slug"), cast("bool", a.json))


def _cmd_list(a: argparse.Namespace) -> int:
    return listing.run_list()


def _cmd_drop(a: argparse.Namespace) -> int:
    return review.drop(_items(a, "slugs"), cast("bool", a.yes))


def _cmd_themes(a: argparse.Namespace) -> int:
    return listing.run_themes(cast("dict[str, str] | None", a.theme))


def _cmd_hashes(a: argparse.Namespace) -> int:
    from walldye.tools import check

    return check.hashes_main(_items(a, "args"))


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="walldye", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # An explicit metavar keeps the hidden _hashes out of the usage line.
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{" + COMMANDS + "}")
    env_theme = os.environ.get("WALLDYE_THEME", "")
    theme = argparse.ArgumentParser(add_help=False)
    theme.add_argument(
        "--theme",
        type=_seeds,
        default=env_theme if env_theme != "" else DEFAULT_THEME,
        metavar="TOKEN",
        help="preset or bg-fg-accent seeds (default: $WALLDYE_THEME, else fireproof)",
    )
    targets = argparse.ArgumentParser(add_help=False)
    targets.add_argument("slugs", nargs="*", type=_slug)
    targets.add_argument("--all", action="store_true", help="every piece in wallpapers/")
    canvas = argparse.ArgumentParser(add_help=False)
    canvas.add_argument(
        "--aspect", type=_aspect, default="16:9", help="e.g. 21:9, 9:19.5 (default 16:9)"
    )
    crop = argparse.ArgumentParser(add_help=False)
    crop.add_argument("--crop", type=_crop, metavar="X,Y,W,H", help="canvas-unit box to zoom into")
    one = argparse.ArgumentParser(add_help=False)
    one.add_argument(
        "--variant", default="default", metavar="NAME", help="a named version (default: default)"
    )
    every = argparse.ArgumentParser(add_help=False)
    every.add_argument("--variant", metavar="NAME", help="only this version (default: all)")
    every.add_argument(
        "--jobs",
        type=_positive,
        metavar="N",
        help="processes, one version of a piece each (default: cores)",
    )
    sets = argparse.ArgumentParser(add_help=False)
    sets.add_argument(
        "--set", action="append", metavar="K=V", help="override one param (repeatable)"
    )

    s = sub.add_parser("new", help="scaffold wallpapers/<slug>/ (design.py + draft meta.yaml)")
    s.add_argument("slug")
    s.add_argument("--model", required=True, help="model id, e.g. claude-opus-5-5")
    s.set_defaults(fn=_cmd_new)

    s = sub.add_parser(
        "preview",
        parents=[theme, canvas, crop, one, sets],
        help="draw a PNG to $WALLDYE_PREVIEW and print lint hints",
    )
    s.add_argument("slug", type=_slug)
    s.add_argument("--width", type=_positive, default=1280, help="long side in px (default 1280)")
    s.add_argument("--renderer", choices=["resvg", "inkscape"], default="resvg")
    s.set_defaults(fn=_cmd_preview)

    s = sub.add_parser(
        "render",
        parents=[theme, canvas, crop, one, sets],
        help="write one SVG (default ./<slug>[--<variant>]-<theme>-<aspect>.svg)",
    )
    s.add_argument("slug", type=_slug)
    s.add_argument(
        "-o", "--output", metavar="PATH", help="output file (.svg, or .png), or - for stdout"
    )
    s.add_argument(
        "--width",
        type=_positive,
        metavar="PX",
        help="a PNG's width; its height follows the aspect (default: the canvas's)",
    )
    s.add_argument(
        "--fit",
        action="store_true",
        help="cut an aspect the piece doesn't declare from 16:9 around its focus, as the site does",
    )
    s.set_defaults(fn=_cmd_render)

    s = sub.add_parser(
        "check",
        parents=[targets, every],
        help="design lint, determinism, recolor fit and variant checks (errors exit 1)",
    )
    s.add_argument(
        "--paranoid", action="store_true", help="also redraw from a fresh import per theme"
    )
    s.add_argument(
        "--similar", action="store_true", help="also list near-clone pairs and skipped pieces"
    )
    s.set_defaults(fn=_cmd_check, need_targets=True)

    s = sub.add_parser(
        "build",
        parents=[targets, every],
        help="check, then write build/ templates, slots.json and index.json",
    )
    s.add_argument("--set", action="append", help=argparse.SUPPRESS)  # refused in main()
    s.add_argument("--published", action="store_true", help="skip draft pieces and draft versions")
    # walldye/tools/ is outside every hash, so a tools change alone never triggers a rebuild.
    s.add_argument("--force", action="store_true", help="rebuild even when slots.json is current")
    s.set_defaults(fn=_cmd_build, need_targets=True)

    s = sub.add_parser(
        "review", help="decide drafts and edit their words in a localhost page; blocks until Apply"
    )
    s.add_argument("slugs", nargs="*", type=_slug, help="default: every draft piece or version")
    s.add_argument("--all", action="store_true", help="every version of every piece, drafts first")
    s.add_argument(
        "--timeout", type=float, default=7200, help="seconds to wait for Apply (default 7200)"
    )
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--no-open", action="store_true", help="don't open a browser")
    s.set_defaults(fn=_cmd_review)

    s = sub.add_parser(
        "sheet",
        parents=[targets, theme, canvas, one, sets],
        help="contact sheet of built templates, or of one slug over --wedge/--seeds",
    )
    s.add_argument(
        "--wedge", action="append", metavar="K=SPEC", help="a..b..step or v1,v2,... (repeatable)"
    )
    s.add_argument("--seeds", metavar="A..B", help="set seed to each of A..B")
    s.add_argument("--cols", type=_positive, help="thumbnails per row")
    s.add_argument("--thumb", type=_positive, default=480, help="thumbnail width in px")
    s.add_argument(
        "-o", "--output", metavar="PATH", help="default $WALLDYE_PREVIEW/sheet-<...>.png"
    )
    s.set_defaults(fn=_cmd_sheet, need_targets=True)

    s = sub.add_parser("params", help="a design's params, ranges and variants")
    s.add_argument("slug", type=_slug)
    s.add_argument("--json", action="store_true", help="as JSON, for scripts")
    s.set_defaults(fn=_cmd_params)

    s = sub.add_parser(
        "list", help="slug, title, description, draft, aspects and variants, tab-separated"
    )
    s.set_defaults(fn=_cmd_list)

    s = sub.add_parser("drop", help="delete wallpapers/<slug>/ after confirmation")
    s.add_argument("slugs", nargs="+", type=_slug)
    s.add_argument(
        "--yes", action="store_true", help="skip the y/N prompt (the owner already confirmed)"
    )
    s.set_defaults(fn=_cmd_drop)

    s = sub.add_parser("themes", help="list presets, or one theme's tokens")
    s.add_argument(
        "--theme", type=_seeds, metavar="TOKEN", help="also print this theme's 21 tokens"
    )
    s.set_defaults(fn=_cmd_themes)

    # check's determinism subprocess: WALLPAPERS_DIR SLUG@VARIANT@ASPECT@REGIME...
    s = sub.add_parser("_hashes")
    s.add_argument("args", nargs="*")
    s.set_defaults(fn=_cmd_hashes)
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command in `argv` (default sys.argv[1:]) and return its exit code; usage
    errors exit 2."""
    ap = _parser()
    a = ap.parse_args(argv)
    cmd = _str(a, "cmd")
    if getattr(a, "need_targets", False) is True:
        if a.all and len(_items(a, "slugs")) > 0:
            ap.error(f"{cmd}: pass slugs or --all, not both")
        if not (a.all or len(_items(a, "slugs")) > 0):
            ap.error(f"{cmd}: name the slugs, or pass --all")
    if cmd == "build" and len(_items(a, "set")) > 0:
        ap.error(SET_REFUSED)
    fn = cast("Command", a.fn)
    try:
        return fn(a)
    except common.UsageError as e:
        ap.error(str(e))

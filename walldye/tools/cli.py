"""walldye: scaffold, preview, check, build, render, review and sheet the wallpapers in wallpapers/<slug>/.

Commands that take slugs need them named (or --all); only `build --verify` and `themes` cover
everything by default, and `review` defaults to the drafts. --theme takes a preset name or
bg-fg-accent hex seeds (also bg,fg,accent and bg=..,fg=..,accent=..).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import walldye
from walldye.tools import common, listing, new, preview, review, sheet

COMMANDS = "new,preview,render,check,build,review,sheet,list,drop,themes"


def _seeds(value: str) -> dict[str, str]:
    try:
        return walldye.parse_seeds(value)
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


def _cmd_new(a) -> int:
    return new.run(a.slug, a.author, a.model)


def _cmd_preview(a) -> int:
    return preview.run(a.slug, a.theme, a.aspect, a.crop, a.width, a.renderer)


def _cmd_render(a) -> int:
    try:
        declared = common.design_aspects(a.slug)
    except ValueError as e:
        sys.exit(str(e))
    if not walldye.supports(declared, a.aspect):
        sys.exit(f"{a.slug} declares ASPECTS={declared}, not {a.aspect}; render 16:9 with --crop instead")
    svg = common.render(a.slug, a.theme, a.aspect)
    if a.crop:
        svg = common.crop_svg(svg, a.crop)
    if a.output == "-":
        sys.stdout.write(svg)
        return 0
    crop = "-crop" if a.crop else ""
    out = Path(a.output or f"{a.slug}-{walldye.theme_token(a.theme)}-{walldye.aspect_label(a.aspect)}{crop}.svg")
    wallpapers, target = common.WALLPAPERS.resolve(), out.resolve()
    if target.is_relative_to(wallpapers) and target.relative_to(wallpapers).parts[1:2] == ("build",):
        sys.exit(f"refusing to write {out}: only walldye build writes into build/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    print(out)
    return 0


def _cmd_check(a) -> int:
    from walldye.tools import check

    return check.run(a.slugs, all=a.all, set_mode=a.set)


def _cmd_build(a) -> int:
    from walldye.tools import build

    return build.run(a.slugs, all=a.all, verify=a.verify, force=a.force)


def _cmd_review(a) -> int:
    return review.run(a.slugs, a.timeout, a.port, not a.no_open)


def _cmd_sheet(a) -> int:
    return sheet.run(common.slugs() if a.all else a.slugs, a.theme, a.cols, a.thumb, a.output)


def _cmd_list(a) -> int:
    return listing.run_list()


def _cmd_drop(a) -> int:
    return review.drop(a.slugs, a.yes)


def _cmd_themes(a) -> int:
    return listing.run_themes(a.theme, a.json)


def _cmd_hashes(a) -> int:
    from walldye.tools import check

    return check.hashes_main(a.args)


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="walldye", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # An explicit metavar keeps the hidden _hashes out of the usage line.
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{" + COMMANDS + "}")
    theme = argparse.ArgumentParser(add_help=False)
    theme.add_argument(
        "--theme",
        type=_seeds,
        default=os.environ.get("WALLDYE_THEME") or walldye.DEFAULT_THEME,
        metavar="TOKEN",
        help="preset or bg-fg-accent seeds (default: $WALLDYE_THEME, else fireproof)",
    )
    targets = argparse.ArgumentParser(add_help=False)
    targets.add_argument("slugs", nargs="*", type=_slug)
    targets.add_argument("--all", action="store_true", help="every piece in wallpapers/")
    canvas = argparse.ArgumentParser(add_help=False)
    canvas.add_argument("--aspect", type=_aspect, default="16:9", help="e.g. 21:9, 9:19.5 (default 16:9)")
    canvas.add_argument("--crop", type=_crop, metavar="X,Y,W,H", help="canvas-unit box to zoom into")

    s = sub.add_parser("new", help="scaffold wallpapers/<slug>/ (design.py + draft meta.yaml)")
    s.add_argument("slug")
    s.add_argument("--author", required=True, help='display name, e.g. "Claude Opus 5.5"')
    s.add_argument("--model", required=True, help="model id, e.g. claude-opus-5-5")
    s.set_defaults(fn=_cmd_new)

    s = sub.add_parser("preview", parents=[theme, canvas], help="render a PNG to $WALLDYE_PREVIEW and print lint hints")
    s.add_argument("slug", type=_slug)
    s.add_argument("--width", type=_positive, default=1280, help="long side in px (default 1280)")
    s.add_argument("--renderer", choices=["resvg", "inkscape"], default="resvg")
    s.set_defaults(fn=_cmd_preview)

    s = sub.add_parser("render", parents=[theme, canvas], help="write one SVG (default ./<slug>-<theme>-<aspect>.svg)")
    s.add_argument("slug", type=_slug)
    s.add_argument("-o", "--output", metavar="PATH", help="output file, or - for stdout")
    s.set_defaults(fn=_cmd_render)

    s = sub.add_parser("check", parents=[targets], help="determinism, skeleton, fit and lint checks (errors exit 1)")
    s.add_argument("--set", action="store_true", help="also list near-clone pairs and skipped pieces")
    s.set_defaults(fn=_cmd_check, need_targets=True)

    s = sub.add_parser("build", parents=[targets], help="check, then write build/ templates, slots.json and index.json")
    s.add_argument("--verify", action="store_true", help="re-render committed templates and diff, writing nothing")
    # walldye/tools/ is outside every hash, so a fit or lint change alone never triggers a rebuild.
    s.add_argument("--force", action="store_true", help="rebuild even when slots.json is current")
    s.set_defaults(fn=_cmd_build, need_targets=True)

    s = sub.add_parser("review", help="approve drafts in a localhost page; blocks until Done")
    s.add_argument("slugs", nargs="*", type=_slug, help="default: every draft: true piece")
    s.add_argument("--timeout", type=float, default=7200, help="seconds to wait for Done (default 7200)")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--no-open", action="store_true", help="don't open a browser")
    s.set_defaults(fn=_cmd_review)

    s = sub.add_parser(
        "sheet", parents=[targets, theme], help="contact sheet of build/16x9.svg, recoloured with --theme"
    )
    s.add_argument("--cols", type=_positive, default=4)
    s.add_argument("--thumb", type=_positive, default=480, help="thumbnail width in px")
    s.add_argument("-o", "--output", metavar="PATH", help="default $WALLDYE_PREVIEW/sheet-<theme>.png")
    s.set_defaults(fn=_cmd_sheet, need_targets=True)

    s = sub.add_parser("list", help="slug, title, description, draft and native aspects, tab-separated")
    s.set_defaults(fn=_cmd_list)

    s = sub.add_parser("drop", help="delete wallpapers/<slug>/ after confirmation")
    s.add_argument("slugs", nargs="+", type=_slug)
    s.add_argument("--yes", action="store_true", help="skip the y/N prompt (the owner already confirmed)")
    s.set_defaults(fn=_cmd_drop)

    s = sub.add_parser("themes", help="list presets; --json writes the vitest theme fixture")
    s.add_argument("--theme", type=_seeds, metavar="TOKEN", help="also print this theme's 21 tokens")
    s.add_argument("--json", action="store_true", help="write src/lib/__fixtures__/themes.json")
    s.set_defaults(fn=_cmd_themes)

    s = sub.add_parser("_hashes")  # check's determinism subprocess: WALLPAPERS_DIR SLUG@ASPECT@THEME...
    s.add_argument("args", nargs="*")
    s.set_defaults(fn=_cmd_hashes)
    return ap


def main(argv: list[str] | None = None) -> int:
    """Run the command in `argv` (default sys.argv[1:]) and return its exit code; usage errors exit 2."""
    ap = _parser()
    a = ap.parse_args(argv)
    if getattr(a, "need_targets", False):
        if a.all and a.slugs:
            ap.error(f"{a.cmd}: pass slugs or --all, not both")
        if not (a.all or a.slugs or getattr(a, "verify", False)):
            ap.error(f"{a.cmd}: name the slugs, or pass --all")
    return a.fn(a)

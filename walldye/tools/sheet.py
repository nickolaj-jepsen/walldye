"""`walldye sheet`: a contact-sheet PNG of the committed build/16x9.svg templates."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import walldye
from walldye.tools import common
from walldye.tools.preview import preview_dir


def themed(slug: str, seeds: dict[str, str]) -> str:
    """The committed 16:9 template of `slug` recoloured to `seeds` the way the site does it:
    build.select picks the slots.json entry (dark-only pieces swap bg and fg under light seeds)
    and build.recolour applies it. Fireproof's exact seeds return build/16x9.svg untouched
    without reading slots.json. KeyError if slots.json lacks the entry."""
    b = common.build_dir(slug)
    if walldye.theme_token(seeds) == "fireproof":
        return (b / "16x9.svg").read_text()
    from walldye.tools.build import load_slots, recolour, select

    slots = load_slots(slug)
    key, applied = select(slots, "16:9", seeds)
    return recolour((b / slots[key]["file"]).read_text(), slots[key], applied)


def run(slugs: list[str], seeds: dict[str, str], cols: int, thumb: int, out: str | None) -> int:
    """Write a sheet of `slugs` (thumbnails `thumb` px wide, `cols` per row, slug labels) under
    `seeds` to `out`, default preview_dir()/sheet-<token>.png, and print its path. Pieces
    without build/16x9.svg and build/slots.json are skipped with a note; exits if none is left."""
    thumbs = []
    for slug in slugs:
        if not all((common.build_dir(slug) / f).exists() for f in ("16x9.svg", "slots.json")):
            print(f"skip {slug}: not built (run walldye build {slug})", file=sys.stderr)
            continue
        thumbs.append((slug, common.rasterise(themed(slug, seeds), thumb)))
    if not thumbs:
        sys.exit("nothing to put on a sheet")
    pad, label = 8, 22
    th = max(im.height for _, im in thumbs)
    cols = min(cols, len(thumbs))
    rows = -(-len(thumbs) // cols)
    sheet = Image.new("RGB", (cols * (thumb + pad) + pad, rows * (th + pad + label) + pad), "black")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=14)
    for k, (slug, im) in enumerate(thumbs):
        x, y = pad + (k % cols) * (thumb + pad), pad + (k // cols) * (th + pad + label)
        sheet.paste(im, (x, y))
        draw.text((x + 4, y + im.height + 3), slug, fill="#DAD8CE", font=font)
    path = Path(out) if out else preview_dir() / f"sheet-{walldye.theme_token(seeds)}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print(path)
    return 0

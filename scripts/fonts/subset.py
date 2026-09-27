#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.66.0", "brotli==1.2.0"]
# ///
"""Rebuild src/assets/fonts/*.woff2 from the pinned upstream fonts listed in SOURCES.md.

Usage: `uv run scripts/fonts/subset.py`. Downloads are cached in scripts/fonts/.cache/ and
checked against their sha256. Exits non-zero if any output fails verification.
"""

import hashlib
import io
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

from fontTools.subset import Options, Subsetter, parse_unicodes
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import AxisTriple, instantiateVariableFont

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT = HERE.parents[1] / "src" / "assets" / "fonts"

GOOGLE_FONTS = "https://raw.githubusercontent.com/google/fonts/f8c1d3d6cc75e30d77130bdcbfbff27e3b6233fe/ofl/ebgaramond"
MONASPACE = (
    "https://github.com/githubnext/monaspace/releases/download/v1.400/monaspace-variable-v1.400.zip"
)
KRYPTON_MEMBER = "Variable Fonts/Monaspace Krypton/Monaspace Krypton Var.ttf"

SOURCES = {
    "EBGaramond[wght].ttf": (
        f"{GOOGLE_FONTS}/EBGaramond%5Bwght%5D.ttf",
        "ef9512f92f6d579e5dc75af59a5a4b1b8b47d2eda89e00b954d44520e5369027",
    ),
    "EBGaramond-Italic[wght].ttf": (
        f"{GOOGLE_FONTS}/EBGaramond-Italic%5Bwght%5D.ttf",
        "bba2c4499c93c9612b90b9825d32b07da52fce2fe57562a1eb6b833553f93c4e",
    ),
    "monaspace-variable-v1.400.zip": (
        MONASPACE,
        "b69a7f2a3c455c89dcb6cc23b61bb3fb8beecba728ccdebeccd80577e58de0c8",
    ),
}

# The pyftsubset command in docs/design.md (Site > Direction), applied to all three faces.
UNICODES = "U+20-7E,U+A0-FF,U+152-153,U+2009-200A,U+2010-203A,U+2060,U+2190-2199,U+2212"
FEATURES = ["kern", "liga", "smcp", "c2sc", "onum", "lnum", "pnum", "tnum", "case"]
# pyftsubset keeps IDs 0-6; 13 and 14 carry the OFL notice inside every served file.
NAME_IDS = [0, 1, 2, 3, 4, 5, 6, 13, 14]

SITE_CHARS = "·×°↗←→↑↓…–—‘’“”−Œœ"
OFL_NOTICE = "This Font Software is licensed under the SIL Open Font License, Version 1.1."
OFL_URL = "https://openfontlicense.org"

MONO_FAMILY = "Walldye Mono"
MONO_PS = "WalldyeMono"
# Monaspace Krypton ships wght 200-800, wdth 100-125 and slnt -11-0; the site uses upright
# normal-width text, so wdth and slnt are pinned and wght keeps Regular through Bold.
MONO_AXES = {"wdth": 100, "slnt": 0, "wght": AxisTriple(400, 400, 700)}
RESERVED = re.compile(r"monaspace|krypton", re.IGNORECASE)


def fetch(name: str) -> Path:
    """Return the cached upstream file `name`, downloading it first if absent.

    Raises SystemExit when the file's sha256 differs from the pin in SOURCES.
    """
    url, sha = SOURCES[name]
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        print(f"fetch {url}")
        tmp = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(path)
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != sha:
        sys.exit(f"{name}: sha256 {got}, expected {sha}; delete it from {CACHE} to refetch")
    return path


def subset(font: TTFont) -> None:
    """Subset `font` in place to UNICODES, FEATURES and NAME_IDS (plus names fvar/STAT use)."""
    subsetter = Subsetter(Options(layout_features=FEATURES, name_IDs=NAME_IDS))
    subsetter.populate(unicodes=parse_unicodes(UNICODES))
    subsetter.subset(font)


def rename_mono(font: TTFont, copyright: str) -> None:
    """Replace every name record carrying a Reserved Font Name, keeping `copyright` as ID 0."""
    name = font["name"]
    name.names = [r for r in name.names if r.nameID >= 256]
    for rec in name.names:
        rec.string = rec.toUnicode().replace("MonaspaceKryptonVar", MONO_PS)
    for name_id, text in {
        0: copyright,
        1: MONO_FAMILY,
        2: "Regular",
        3: f"1.400;UKWN;{MONO_PS}-Regular",
        4: f"{MONO_FAMILY} Regular",
        5: "Version 1.400",
        6: f"{MONO_PS}-Regular",
        13: OFL_NOTICE,
        14: OFL_URL,
    }.items():
        name.setName(text, name_id, 3, 1, 0x409)


def build_garamond(src: Path, out: Path) -> None:
    font = TTFont(src, recalcTimestamp=False)
    subset(font)
    font.flavor = "woff2"
    font.save(out)


def build_mono(zip_path: Path, out: Path) -> None:
    with zipfile.ZipFile(zip_path) as z:
        font = TTFont(io.BytesIO(z.read(KRYPTON_MEMBER)), recalcTimestamp=False)
    # Upstream has no ID 0; its copyright notice (with the RFN statement) sits in ID 7.
    copyright = font["name"].getDebugName(7)
    if not copyright or "GitHub" not in copyright:
        sys.exit(f"Krypton name ID 7 is not the expected copyright notice: {copyright!r}")
    font = instantiateVariableFont(font, MONO_AXES)
    # Subsetting the instancer's in-memory result raises KeyError in gvar; a round-trip avoids it.
    buf = io.BytesIO()
    font.save(buf)
    font = TTFont(io.BytesIO(buf.getvalue()), recalcTimestamp=False)
    subset(font)
    rename_mono(font, copyright)
    font.flavor = "woff2"
    font.save(out)


def single_subs(font: TTFont, tag: str) -> dict[str, str]:
    """Return the single substitutions reachable from GSUB feature `tag` (empty if absent)."""
    gsub = font["GSUB"].table
    mapping: dict[str, str] = {}
    for record in gsub.FeatureList.FeatureRecord:
        if record.FeatureTag != tag:
            continue
        for index in record.Feature.LookupListIndex:
            lookup = gsub.LookupList.Lookup[index]
            for sub in lookup.SubTable:
                sub = getattr(sub, "ExtSubTable", sub)
                mapping.update(getattr(sub, "mapping", {}))
    return mapping


def features(font: TTFont, table: str) -> list[str]:
    if table not in font:
        return []
    return sorted({r.FeatureTag for r in font[table].table.FeatureList.FeatureRecord})


def verify(out: Path, upstream: TTFont, garamond: bool) -> list[str]:
    """Check `out` against `upstream` and print a summary; return the failures."""
    font = TTFont(out)
    cmap = font.getBestCmap()
    wanted = set(parse_unicodes(UNICODES))
    upstream_cmap = upstream.getBestCmap()
    errors = []

    lost = sorted(u for u in wanted & upstream_cmap.keys() if u not in cmap)
    if lost:
        errors.append(f"dropped codepoints: {' '.join(f'U+{u:04X}' for u in lost)}")
    absent = [c for c in SITE_CHARS if ord(c) not in cmap]
    if absent:
        errors.append(f"site characters missing: {''.join(absent)}")

    if garamond:
        for tag, char in (("smcp", "a"), ("c2sc", "A"), ("onum", "1")):
            if cmap.get(ord(char)) not in single_subs(font, tag):
                errors.append(f"{tag} does not substitute {char!r}")
        # Thin and hair spaces set "1920 × 1080"; the mono has neither, and no face has U+202F.
        if not {0x2009, 0x200A} <= cmap.keys():
            errors.append("thin or hair space missing")
        if font["name"].getDebugName(1) != "EB Garamond":
            errors.append(f"family is {font['name'].getDebugName(1)!r}")
    else:
        expect = {
            1: MONO_FAMILY,
            2: "Regular",
            4: f"{MONO_FAMILY} Regular",
            6: f"{MONO_PS}-Regular",
        }
        for name_id, text in expect.items():
            if font["name"].getDebugName(name_id) != text:
                errors.append(f"name ID {name_id} is {font['name'].getDebugName(name_id)!r}")
        for rec in font["name"].names:
            if rec.nameID != 0 and RESERVED.search(rec.toUnicode()):
                errors.append(
                    f"name ID {rec.nameID} keeps a Reserved Font Name: {rec.toUnicode()!r}"
                )

    gaps = sorted(wanted - upstream_cmap.keys())
    axes = (
        ", ".join(f"{a.axisTag} {a.minValue:g}-{a.maxValue:g}" for a in font["fvar"].axes)
        if "fvar" in font
        else "static"
    )
    print(
        f"{out.name}: {out.stat().st_size} bytes, {len(font.getGlyphOrder())} glyphs, {len(cmap)} codepoints, {axes}"
    )
    print(f"  family {font['name'].getDebugName(1)!r}, usWeightClass {font['OS/2'].usWeightClass}")
    print(
        f"  GSUB {' '.join(features(font, 'GSUB'))}; GPOS {' '.join(features(font, 'GPOS')) or '-'}"
    )
    if gaps:
        print(f"  not in upstream: {' '.join(f'U+{u:04X}' for u in gaps)}")
    for e in errors:
        print(f"  FAIL {e}")
    return errors


def main() -> None:
    sources = (HERE / "SOURCES.md").read_text()
    unrecorded = [n for n, (_, sha) in SOURCES.items() if sha not in sources]
    if unrecorded:
        sys.exit(f"SOURCES.md is missing the sha256 of: {', '.join(unrecorded)}")

    roman = fetch("EBGaramond[wght].ttf")
    italic = fetch("EBGaramond-Italic[wght].ttf")
    monaspace = fetch("monaspace-variable-v1.400.zip")
    OUT.mkdir(parents=True, exist_ok=True)

    build_garamond(roman, OUT / "eb-garamond-roman.woff2")
    build_garamond(italic, OUT / "eb-garamond-italic.woff2")
    build_mono(monaspace, OUT / "walldye-mono.woff2")

    with zipfile.ZipFile(monaspace) as z:
        krypton = TTFont(io.BytesIO(z.read(KRYPTON_MEMBER)))
    errors = [
        *verify(OUT / "eb-garamond-roman.woff2", TTFont(roman), garamond=True),
        *verify(OUT / "eb-garamond-italic.woff2", TTFont(italic), garamond=True),
        *verify(OUT / "walldye-mono.woff2", krypton, garamond=False),
    ]
    if errors:
        sys.exit(f"{len(errors)} verification failure(s)")


if __name__ == "__main__":
    main()

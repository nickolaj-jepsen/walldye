"""The Python-made fixtures vitest's parity tests check the TS ports against.

`uv run python scripts/fixtures/regen.py` writes them to tests/fixtures/, uncommitted:
themes.json, constants.json, crops.json and collision/, and the reference renders, which need
REFERENCE_PIECES built first. CI runs it after `walldye build`; run it locally before
`pnpm test`. The hand-written specs the ports also read (tokenize.json, theme-tokens.json) are
committed in src/lib/__fixtures__/.
"""

import contextlib
import importlib.metadata
import io
import json
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

import resvg_py
from PIL import Image

from walldye import _design, _theme
from walldye._aspect import SITE_ASPECTS, canvas_size
from walldye.tools import build, common, hashing, lint
from walldye.tools import themes as check_themes
from walldye.tools.paths import aspect_label
from walldye.tools.themes import parse_seeds
from walldye.tools.tokenize import find_colors

sys.path.insert(0, str(common.ROOT / "tests/python"))
from fixtures.pieces import RECOLOR_THEMES, install

REFERENCE = common.ROOT / "tests/fixtures"
# Every template of these pieces gets reference renders under RECOLOR_THEMES.
REFERENCE_PIECES = ["dither-moon", "radar-sweep", "schotter"]
# The resvg-wasm parity reference: slug, aspect, theme, width in px.
RESVG = ("schotter", "16:9", "nord", 960)
THEMES_SEED, THEMES_PER_REGIME = 1, 20
# Seed triples where regime selection is closest to a tie.
EDGE_CASES = [
    ("#808080", "#808080", "#CF6A4C"),
    ("#777777", "#787878", "#CF6A4C"),
    ("#787878", "#777777", "#CF6A4C"),
]
# Where the crops are centered, as fractions of the canvas: both edges, the middle and between.
CROP_FOCI = [(0.0, 0.0), (0.25, 0.8), (0.5, 0.5), (0.8, 0.1), (1.0, 1.0), (0.3337, 0.6663)]


def _entry(seeds: dict[str, str]) -> dict[str, object]:
    return {
        "seeds": seeds,
        "light": _theme.is_light(seeds["bg"], seeds["fg"]),
        "tokens": _theme.theme_tokens(seeds),
    }


def themes() -> dict[str, object]:
    """The theme port's reference data: every preset, THEMES_PER_REGIME random seed triples per
    regime from check_themes.generate(THEMES_SEED, ...), and EDGE_CASES, each as {seeds, light,
    tokens} with tokens in TOKENS order (fireproof's exact seeds resolve to its pinned table)."""
    random = check_themes.generate(THEMES_SEED, THEMES_PER_REGIME)
    return {
        "presets": {name: _entry(check_themes.parse_seeds(name)) for name in check_themes.PRESETS},
        "random": {
            r: [_entry(dict(zip(_theme.SEEDS, t, strict=True))) for t in triples]
            for r, triples in random.items()
        },
        "edges": [_entry(dict(zip(_theme.SEEDS, t, strict=True))) for t in EDGE_CASES],
    }


def constants() -> dict[str, object]:
    """The constants the site defines again in TypeScript."""
    return {
        "site_aspects": list(SITE_ASPECTS),
        "canvas": {a: list(canvas_size(a)) for a in SITE_ASPECTS},
        "reserved_slugs": sorted(lint.RESERVED_SLUGS),
        "color_words": sorted(lint.COLOR_WORDS),
        "max_variants": _design.MAX_VARIANTS,
        "default_license": lint.DEFAULT_LICENSE,
        "fan_work": lint.FAN_WORK,
    }


def crops() -> list[dict[str, object]]:
    """fit_crop's position and box for each site aspect but 16:9 around each of CROP_FOCI."""
    return [
        {
            "aspect": aspect,
            "focus": list(focus),
            "t": common.crop_position(aspect, focus),
            "box": list(common.fit_crop(aspect, focus)),
        }
        for aspect in SITE_ASPECTS[1:]
        for focus in CROP_FOCI
    ]


def per_hex(slug: str) -> dict[str, object]:
    """The built dark 16:9 slot table of `slug` keyed by fireproof hex instead of by
    occurrence: each distinct template hex takes the coefficients of its first slot."""
    slots = build.load_slots(slug)
    assert slots is not None, f"{slug} is not built"
    entry = build.entries(slots)["16:9/dark"]
    template = [c for _, _, c in find_colors((common.build_dir(slug) / entry["file"]).read_text())]
    first: dict[str, int] = {}
    for i, c in enumerate(template):
        first.setdefault(c, i)
    hexes = list(first)
    return {
        "n": len(template),
        "coefs": [entry["coefs"][entry["occ"][first[h]]] for h in hexes],
        "occ": [hexes.index(c) for c in template],
    }


def collision() -> dict[str, str]:
    """The collision piece as build writes it, its renders under RECOLOR_THEMES and its
    per-hex table."""
    saved = common.WALLPAPERS
    with tempfile.TemporaryDirectory() as tmp:
        common.WALLPAPERS = Path(tmp)
        try:
            install(common.WALLPAPERS, "collision")
            with contextlib.redirect_stdout(io.StringIO()) as log:
                if build.run(["collision"]) != 0:
                    raise RuntimeError(f"collision fixture failed to build:\n{log.getvalue()}")
            b = common.build_dir("collision")
            renders = {t: common.render("collision", t) for t in RECOLOR_THEMES}
            return {
                "collision/16x9.svg": (b / "16x9.svg").read_text(),
                "collision/slots.json": (b / "slots.json").read_text(),
                "collision/renders.json": json.dumps(renders, indent=1) + "\n",
                "collision/per-hex.json": json.dumps(per_hex("collision")) + "\n",
            }
        finally:
            common.WALLPAPERS = saved


def outputs() -> dict[str, str]:
    """The fixtures that need no build, path relative to tests/fixtures/ -> text."""
    return {
        "themes.json": json.dumps(themes(), indent=2) + "\n",
        "constants.json": json.dumps(constants(), indent=1) + "\n",
        "crops.json": json.dumps(crops(), indent=1) + "\n",
        **collision(),
    }


def _rel(path: Path) -> str:
    return path.relative_to(common.ROOT).as_posix()


def _png(svg: str, width: int, height: int, background: str) -> bytes:
    """RGB PNG of `svg` from resvg-py, called the way the site's export worker calls resvg-wasm."""
    data = resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height, background=background)
    out = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(out, "PNG")
    return out.getvalue()


def references_current() -> bool:
    """Whether every REFERENCE_PIECES build matches its design and the render inputs, so
    references() can be made."""
    lib_sha = hashing.render_lib_sha()
    for slug in REFERENCE_PIECES:
        slots = build.load_slots(slug)
        if (
            slots is None
            or slots.get("design_sha") != hashing.design_sha(slug)
            or slots.get("render_lib") != lib_sha
        ):
            return False
    return True


def references() -> dict[str, str | bytes]:
    """tests/fixtures/ for the builds of REFERENCE_PIECES, path relative to it -> content.

    - `<slug>/<aspect>.<theme>.svg`: a Python render under each RECOLOR_THEMES theme;
    - `resvg/`: the RESVG recolor as SVG and its resvg-py PNG;
    - `manifest.json`: what each file is, and the design_sha and template sha256 it was made from.
    """
    out: dict[str, str | bytes] = {}
    renders = []
    pieces = {}
    for slug in REFERENCE_PIECES:
        slots = build.load_slots(slug)
        assert slots is not None, f"{slug} is not built"
        table = build.entries(slots)
        pieces[slug] = {"design_sha": slots["design_sha"]}
        for aspect in dict.fromkeys(k.split("/")[0] for k in table):
            for theme in RECOLOR_THEMES:
                seeds = parse_seeds(theme)
                key = build.select(slots, aspect, seeds)
                rel = f"{slug}/{aspect_label(aspect)}.{theme}.svg"
                out[rel] = common.render(slug, seeds, aspect)
                renders.append({
                    "slug": slug, "aspect": aspect, "theme": theme, "entry": key,
                    "template": _rel(common.build_dir(slug) / table[key]["file"]), "sha256": table[key]["sha256"],
                    "render": _rel(REFERENCE / rel),
                })  # fmt: skip
    slug, aspect, theme, width = RESVG
    slots = build.load_slots(slug)
    assert slots is not None, f"{slug} is not built"
    table = build.entries(slots)
    seeds = parse_seeds(theme)
    key = build.select(slots, aspect, seeds)
    svg = build.recolor(
        (common.build_dir(slug) / table[key]["file"]).read_text(), table[key], seeds
    )
    w, h = canvas_size(aspect)
    height = round(width * h / w)
    name = f"resvg/{slug}.{aspect_label(aspect)}.{theme}"
    out[f"{name}.svg"] = svg
    out[f"{name}.png"] = _png(svg, width, height, seeds["bg"])
    resvg = {
        "svg": _rel(REFERENCE / f"{name}.svg"), "png": _rel(REFERENCE / f"{name}.png"),
        "width": width, "height": height, "background": seeds["bg"],
        "resvg_py": importlib.metadata.version("resvg-py"),
    }  # fmt: skip
    manifest = {"themes": RECOLOR_THEMES, "pieces": pieces, "renders": renders, "resvg": resvg}
    out["manifest.json"] = json.dumps(manifest, indent=1) + "\n"
    return out


def _write(base: Path, files: Mapping[str, str | bytes]) -> None:
    for rel, content in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        print(path, file=sys.stderr)


if __name__ == "__main__":
    _write(REFERENCE, outputs())
    if not references_current():
        print(f"tests/fixtures/: build {', '.join(REFERENCE_PIECES)} first", file=sys.stderr)
        sys.exit(1)
    _write(REFERENCE, references())

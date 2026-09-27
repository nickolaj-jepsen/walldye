"""The Python-made fixtures vitest checks the TS ports against, and the helper that installs
the synthetic designs in designs/ as pieces.

`uv run python tests/python/fixtures/regen.py` writes them, uncommitted: themes.json and
collision/ in src/lib/__fixtures__/, and the reference renders in tests/fixtures/, which need
REFERENCE_PIECES built first. CI runs it after `walldye build`; run it locally before
`pnpm test`. The hand-written specs next to them (tokenize.json, theme-tokens.json) are
committed.
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
import yaml
from PIL import Image

from walldye._aspect import aspect_label, canvas_size
from walldye._theme import parse_seeds
from walldye.tools import build, common, hashing, listing
from walldye.tools.tokenize import find_colours

HERE = Path(__file__).parent
DESIGNS = HERE / "designs"
SHARED = common.ROOT / "src/lib/__fixtures__"
REFERENCE = common.ROOT / "tests/fixtures"
META = {
    "title": "Fixture",
    "description": "A synthetic design for the build tests.",
    "model": "claude-opus-5-5",
    "draft": True,
}
# vitest (b) themes: a 1-unit neighbour of fireproof (derived model), two presets, and a light
# corner, so each regime is recoloured under two themes other than its template's.
RECOLOUR_THEMES = ["1c1b1b-dad8ce-cf6a4c", "nord", "flexoki-light", "ffffff-000000-0000ff"]
# Every template of these pieces gets reference renders under RECOLOUR_THEMES.
REFERENCE_PIECES = ["dither-moon", "radar-sweep", "schotter"]
# The resvg-wasm parity reference: slug, aspect, theme, width in px.
RESVG = ("schotter", "16:9", "nord", 960)


def install(
    wallpapers: Path,
    design: str,
    slug: str | None = None,
    data: Mapping[str, str] | None = None,
    **meta: object,
) -> str:
    """Copy designs/<design>.py to wallpapers/<slug>/design.py (slug defaults to `design`)
    with META updated by `meta` as its meta.yaml and `data` as data/<name> files, credited by
    a data source unless `meta` gives the sources; returns the slug."""
    slug = slug or design
    if data and "sources" not in meta:
        meta = {**meta, "sources": [{"kind": "data", "topic": "Fixture points"}]}
    d = wallpapers / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "design.py").write_text((DESIGNS / f"{design}.py").read_text())
    (d / "meta.yaml").write_text(yaml.safe_dump({**META, **meta}, sort_keys=False))
    for name, text in (data or {}).items():
        (d / "data").mkdir(exist_ok=True)
        (d / "data" / name).write_text(text)
    return slug


def per_hex(slug: str) -> dict[str, object]:
    """The built dark 16:9 slot table of `slug` keyed by fireproof hex instead of by
    occurrence: each distinct template hex takes the coefficients of its first slot."""
    slots = build.load_slots(slug)
    assert slots is not None, f"{slug} is not built"
    entry = build.entries(slots)["16:9/dark"]
    template = [c for _, _, c in find_colours((common.build_dir(slug) / entry["file"]).read_text())]
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
    """The collision piece as build writes it, its renders under RECOLOUR_THEMES and its
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
            renders = {t: common.render("collision", t) for t in RECOLOUR_THEMES}
            return {
                "collision/16x9.svg": (b / "16x9.svg").read_text(),
                "collision/slots.json": (b / "slots.json").read_text(),
                "collision/renders.json": json.dumps(renders, indent=1) + "\n",
                "collision/per-hex.json": json.dumps(per_hex("collision")) + "\n",
            }
        finally:
            common.WALLPAPERS = saved


def outputs() -> dict[str, str]:
    """The generated fixtures in src/lib/__fixtures__/, path relative to it -> text."""
    return {"themes.json": json.dumps(listing.fixture(), indent=2) + "\n", **collision()}


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

    - `<slug>/<aspect>.<theme>.svg`: a Python render under each RECOLOUR_THEMES theme;
    - `resvg/`: the RESVG recolour as SVG and its resvg-py PNG;
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
            for theme in RECOLOUR_THEMES:
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
    svg = build.recolour(
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
    manifest = {"themes": RECOLOUR_THEMES, "pieces": pieces, "renders": renders, "resvg": resvg}
    out["manifest.json"] = json.dumps(manifest, indent=1) + "\n"
    return out


def _write(base: Path, files: Mapping[str, str | bytes]) -> None:
    for rel, content in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        print(path, file=sys.stderr)


if __name__ == "__main__":
    _write(SHARED, outputs())
    if not references_current():
        print(f"tests/fixtures/: build {', '.join(REFERENCE_PIECES)} first", file=sys.stderr)
        sys.exit(1)
    _write(REFERENCE, references())

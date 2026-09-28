"""Fixtures shared with vitest (src/lib/__fixtures__/ and tests/fixtures/), and the helper that
installs the synthetic designs in designs/ as pieces.

Rewrite them with `uv run python tests/python/fixtures/regen.py` after `walldye build`; the
pytest suite fails while a committed copy is stale. tests/fixtures/ needs the real pieces
built, so it is checked through the template hashes its manifest records rather than rebuilt,
and it is only rewritten once every REFERENCE_PIECES build is current.
"""

import contextlib
import importlib.metadata
import io
import json
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import resvg_py
import yaml
from PIL import Image

from walldye import _basis
from walldye._aspect import aspect_label, canvas_size
from walldye._theme import SEEDS, parse_seeds
from walldye.tools import build, common, fit, hashing
from walldye.tools.tokenize import find_colours

HERE = Path(__file__).parent
DESIGNS = HERE / "designs"
SHARED = common.ROOT / "src/lib/__fixtures__"
REFERENCE = common.ROOT / "tests/fixtures"
META = {
    "title": "Fixture",
    "description": "A synthetic design for the build tests.",
    "ai_generated": True,
    "draft": True,
}
# vitest (b) themes: a 1-unit neighbour of fireproof (derived model), two presets, and a light
# corner, so each regime is recoloured under two themes other than its template's.
RECOLOUR_THEMES = ["1c1b1b-dad8ce-cf6a4c", "nord", "flexoki-light", "ffffff-000000-0000ff"]
# Every template of these pieces gets reference renders under RECOLOUR_THEMES.
REFERENCE_PIECES = ["dither-moon", "radar-sweep", "schotter"]
# The resvg-wasm parity reference: slug, aspect, theme, width in px.
RESVG = ("schotter", "16:9", "nord", 960)
DEFINITION = (
    "sha256 over UTF-8 lines '<key>\\t<value>\\n' sorted by line; a file's key is its"
    " repo-relative posix path, its value the sha256 of its bytes. design_sha covers design.py"
    " (or source.svg and palette.yaml), every file in data/ and a themes line, plus a"
    " 'variant\\t<name>' line for a named variant."
)
# name -> (files, lines): "design" is v1's vector unchanged; "variant-with-data" adds a data
# file and a named variant's line.
HASH_VECTORS: dict[str, tuple[dict[str, str], list[str]]] = {
    "design": (
        {
            "wallpapers/example/design.py": '"""Example."""\n\nfrom walldye import ACCENT\n\n\ndef draw(s):\n    s.circle(960, 540, 100, fill=ACCENT)\n',
        },
        ["themes\tdark,light"],
    ),
    "variant-with-data": (
        {
            "wallpapers/example/design.py": '"""Example."""\n\nfrom walldye import ACCENT, Canvas, P, design\n\n\n@design()\ndef draw(s: Canvas) -> None:\n    s.fill(P().dots(s.data("points.json"), 12), ACCENT)\n',
            "wallpapers/example/data/points.json": "[[960, 540], [1200, 300]]\n",
        },
        ["themes\tdark,light", "variant\tlate"],
    ),
}


def install(
    wallpapers: Path,
    design: str,
    slug: str | None = None,
    data: Mapping[str, str] | None = None,
    **meta: object,
) -> str:
    """Copy designs/<design>.py to wallpapers/<slug>/design.py (slug defaults to `design`)
    with META updated by `meta` as its meta.yaml and `data` as data/<name> files; returns the
    slug."""
    slug = slug or design
    d = wallpapers / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "design.py").write_text((DESIGNS / f"{design}.py").read_text())
    (d / "meta.yaml").write_text(yaml.safe_dump({**META, **meta}, sort_keys=False))
    for name, text in (data or {}).items():
        (d / "data").mkdir(exist_ok=True)
        (d / "data" / name).write_text(text)
    return slug


def per_hex(slug: str, regime: str = "dark") -> dict[str, object]:
    """The slot table a per-hex fit gives `slug` at 16:9: one coefficient row per distinct
    fireproof hex, fitted jointly over every slot showing it (the mean of their colours)."""
    template = [c for _, _, c in find_colours(common.render(slug, "fireproof"))]
    hexes = list(dict.fromkeys(template))
    basis = _basis.BASIS[regime]
    renders = []
    for t in basis:
        colours = fit.colours(common.render(slug, dict(zip(SEEDS, t, strict=True))))
        renders.append(
            np.array(
                [colours[[i for i, c in enumerate(template) if c == h]].mean(axis=0) for h in hexes]
            )
        )
    rows, _ = fit.compact(fit.fit(basis, renders))
    return {"n": len(template), "coefs": rows, "occ": [hexes.index(c) for c in template]}


def hash_vector() -> str:
    vectors = []
    for name, (files, lines) in HASH_VECTORS.items():
        all_lines = [
            *(f"{path}\t{hashing.sha256(text.encode())}" for path, text in files.items()),
            *lines,
        ]
        vectors.append({
            "name": name,
            "files": files,
            "lines": lines,
            "text": "".join(f"{line}\n" for line in sorted(all_lines)),
            "sha256": hashing.digest(all_lines),
        })  # fmt: skip
    return json.dumps({"definition": DEFINITION, "vectors": vectors}, indent=1) + "\n"


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
    """Every shared fixture, path relative to src/lib/__fixtures__/ -> text."""
    specs = {name: (HERE / name).read_text() for name in ("tokenize.json", "theme-tokens.json")}
    return {**specs, "hash-vector.json": hash_vector(), **collision()}


def _rel(path: Path) -> str:
    return path.relative_to(common.ROOT).as_posix()


def _png(svg: str, width: int, height: int, background: str) -> bytes:
    """RGB PNG of `svg` from resvg-py, called the way the site's export worker calls resvg-wasm."""
    data = resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height, background=background)
    out = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(out, "PNG")
    return out.getvalue()


def references_current() -> bool:
    """Whether every REFERENCE_PIECES build is current, so references() can be made."""
    for slug in REFERENCE_PIECES:
        slots = build.load_slots(slug)
        if slots is None or slots.get("checked") != build.version():
            return False
    return True


def references() -> dict[str, str | bytes]:
    """tests/fixtures/ for the committed builds of REFERENCE_PIECES, path relative to it -> content.

    - `<slug>/<aspect>.<theme>.svg`: a Python render under each RECOLOUR_THEMES theme, with the
      seeds build.select applies (bg and fg swapped for a dark-only piece under light seeds);
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
                key, applied = build.select(slots, aspect, parse_seeds(theme))
                rel = f"{slug}/{aspect_label(aspect)}.{theme}.svg"
                out[rel] = common.render(slug, applied, aspect)
                renders.append({
                    "slug": slug, "aspect": aspect, "theme": theme, "entry": key,
                    "template": _rel(common.build_dir(slug) / table[key]["file"]), "sha256": table[key]["sha256"],
                    "render": _rel(REFERENCE / rel),
                })  # fmt: skip
    slug, aspect, theme, width = RESVG
    slots = build.load_slots(slug)
    assert slots is not None, f"{slug} is not built"
    table = build.entries(slots)
    key, applied = build.select(slots, aspect, parse_seeds(theme))
    svg = build.recolour(
        (common.build_dir(slug) / table[key]["file"]).read_text(), table[key], applied
    )
    w, h = canvas_size(aspect)
    height = round(width * h / w)
    name = f"resvg/{slug}.{aspect_label(aspect)}.{theme}"
    out[f"{name}.svg"] = svg
    out[f"{name}.png"] = _png(svg, width, height, applied["bg"])
    resvg = {
        "svg": _rel(REFERENCE / f"{name}.svg"), "png": _rel(REFERENCE / f"{name}.png"),
        "width": width, "height": height, "background": applied["bg"],
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
    if references_current():
        _write(REFERENCE, references())
    else:
        print(
            f"tests/fixtures/ not rewritten: build {', '.join(REFERENCE_PIECES)} first",
            file=sys.stderr,
        )

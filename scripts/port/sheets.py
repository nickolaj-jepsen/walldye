"""Before/after review sheets for the port: each nixos original next to its new 16:9 template.

    uv run python scripts/port/sheets.py [SLUG...] [--after-dir DIR] [--out DIR] [--width PX]

For each slug the nixos original (`~/nixos/modules/desktop/dms/backgrounds/<slug>.svg`, read
only; a `<slug>-branch` folder is compared with `<slug>.svg`) and the new default-variant
template (`wallpapers/<slug>/build/16x9.svg`, or `DIR/<slug>.svg` with --after-dir, as
`smoke.py --svg-dir` writes them before anything is built) are rasterised with resvg at the same
size and compared. The score is the percentage of pixels whose largest channel difference
exceeds 8; mean absolute difference (0-255) and SSIM are reported beside it.

Writes `import/review/index.html` (gitignored), one card per piece sorted by score, highest
first, with the pair, a difference map, the light theme, the other native aspects and the named
variants, and the new meta.yaml copy. Above the cards: the `<slug>`/`<slug>-branch` twins side by
side at every aspect, and lists of the draft pieces and versions, the recreations with their
licence, the fan pieces, and the pieces kept at 16:9 or a few aspects. `import/review/summary.json`
holds the same data. Without slugs every wallpapers/ folder is compared, or every SVG in
--after-dir. Rasters are cached by content in `<out>/.cache`.
"""

import argparse
import hashlib
import html
import io
import json
import os
import re
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import resvg_py
import yaml
from PIL import Image
from skimage.metrics import structural_similarity

from walldye._aspect import SITE_ASPECTS
from walldye._theme import hex_to_rgb, parse_theme, rgb_to_hex
from walldye.tools.tokenize import find_colours, substitute

ROOT = Path(__file__).resolve().parents[2]
NIXOS = Path.home() / "nixos" / "modules" / "desktop" / "dms" / "backgrounds"
THRESHOLD = 8  # a pixel counts as changed above this channel difference (anti-aliasing noise)
LIGHT = "flexoki-light"
STRIP = 300  # raster height of the other native aspects


@dataclass
class Piece:
    slug: str
    status: str = "compared"  # compared | no-original | not-built | error
    note: str = ""
    score: float = 0.0  # % of pixels changed
    mad: float = 0.0  # mean absolute difference, 0-255
    ssim: float = 1.0
    before: str = ""
    after: str = ""
    diff: str = ""
    before_svg: str = ""
    after_svg: str = ""
    light: str = ""
    light_note: str = ""
    variants: list[dict[str, str]] = field(default_factory=list)
    aspects: list[dict[str, str]] = field(default_factory=list)  # native aspects besides 16:9
    native: list[str] = field(default_factory=list)  # every native aspect, from slots.json
    legacy: bool = False  # source.svg, no design.py
    copy: dict[str, object] = field(default_factory=dict)


def viewbox(svg: str) -> tuple[float, float]:
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    return (float(m.group(1)), float(m.group(2))) if m else (16.0, 9.0)


def rasterise(svg: str, width: int, cache: Path) -> Image.Image:
    """RGB raster of `svg` at `width` px (height from the viewBox), cached by content."""
    key = hashlib.sha256(f"{width}\n{svg}".encode()).hexdigest()
    hit = cache / f"{key}.png"
    if hit.exists():
        return Image.open(hit).convert("RGB")
    w, h = viewbox(svg)
    data = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width, height=round(width * h / w)))
    img = Image.open(io.BytesIO(data)).convert("RGB")
    cache.mkdir(parents=True, exist_ok=True)
    img.save(hit)
    return img


def compare(before: Image.Image, after: Image.Image) -> tuple[float, float, float, Image.Image]:
    """(score %, mean abs diff, SSIM, difference map) of two rasters; `after` is resized to
    `before` when their sizes differ."""
    if after.size != before.size:
        after = after.resize(before.size)
    a = np.asarray(before, np.int16)
    b = np.asarray(after, np.int16)
    d = np.abs(a - b)
    worst = d.max(axis=2)
    score = float((worst > THRESHOLD).mean() * 100)
    grey = [np.asarray(im.convert("L"), np.float64) for im in (before, after)]
    ssim = float(structural_similarity(grey[0], grey[1], data_range=255))
    # changed pixels in white, smaller differences as a faint grey
    shade = np.where(worst > THRESHOLD, 255, np.minimum(worst * 12, 120))
    diff = Image.fromarray(shade.astype(np.uint8), "L")
    return round(score, 3), round(float(d.mean()), 3), round(ssim, 4), diff


def recolour(svg: str, entry: dict[str, object], seeds: tuple[str, str, str]) -> str:
    """`svg` recoloured through a slots.json entry the way the site does it."""
    coefs = np.array(entry["coefs"], float).reshape(-1, 6)[np.array(entry["occ"], int)]
    bg, fg, accent = (np.array(hex_to_rgb(c), float) for c in seeds)
    rgb = coefs[:, [0]] * bg + coefs[:, [1]] * fg + coefs[:, [2]] * accent + coefs[:, 3:]
    values = [rgb_to_hex(*row) for row in np.clip(np.rint(rgb), 0, 255)]
    if len(values) != len(find_colours(svg)):
        raise ValueError("slots.json does not match the template")
    return substitute(svg, values)


def light_svg(build: Path) -> tuple[str, str] | None:
    """The 16:9 template under flexoki-light and a caption, or None when it cannot be made."""
    if (build / "16x9.light.svg").exists():
        return (build / "16x9.light.svg").read_text(), "light template"
    slots_path = build / "slots.json"
    if not slots_path.exists() or not (build / "16x9.svg").exists():
        return None
    slots = json.loads(slots_path.read_text())
    theme = parse_theme(LIGHT)
    seeds = (theme["bg"], theme["fg"], theme["accent"])
    if "16:9/light" in slots:
        entry, caption = slots["16:9/light"], f"{LIGHT}, recoloured"
    elif "16:9/dark" in slots:
        entry, caption = slots["16:9/dark"], f"{LIGHT} with its background and foreground swapped"
        seeds = (seeds[1], seeds[0], seeds[2])
    else:
        return None
    template = (build / str(entry["file"])).read_text()
    return recolour(template, entry, seeds), caption


def native_templates(build: Path) -> list[tuple[str, str]]:
    """(aspect, file) of the default version's dark templates, in SITE_ASPECTS order; [] when
    build/slots.json is missing or unreadable."""
    try:
        slots = json.loads((build / "slots.json").read_text())
    except (OSError, ValueError):
        return []
    out: list[tuple[str, str]] = []
    for aspect in SITE_ASPECTS:
        entry = slots.get(f"{aspect}/dark")
        if isinstance(entry, dict) and "file" in entry:
            out.append((aspect, str(entry["file"])))
    return out


def docstring(path: Path) -> str:
    if not path.exists():
        return ""
    m = re.match(r'\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', path.read_text(), re.DOTALL)
    return m.group(1).strip() if m else ""


def meta_copy(folder: Path) -> tuple[dict[str, object], dict[str, object]]:
    """(meta.yaml as read, the copy a reviewer reads: title, description, notes, docstring,
    licence, franchise, sources and variant labels)."""
    path = folder / "meta.yaml"
    meta = yaml.safe_load(path.read_text()) if path.exists() else {}
    meta = meta if isinstance(meta, dict) else {}
    keep = ("title", "description", "notes", "license", "franchise", "sources", "variants")
    copy = {k: meta[k] for k in keep if k in meta}
    copy["draft"] = meta.get("draft", False)
    copy["docstring"] = docstring(folder / "design.py")
    return meta, copy


def save(img: Image.Image, out: Path, rel: str) -> str:
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=88)
    return rel


def thumb(img: Image.Image, width: int) -> Image.Image:
    return img.resize((width, round(img.height * width / img.width)), Image.Resampling.LANCZOS)


def original_of(slug: str, nixos: Path) -> Path | None:
    for name in (slug, slug.removesuffix("-branch")):
        if (nixos / f"{name}.svg").exists():
            return nixos / f"{name}.svg"
    return None


@dataclass(frozen=True)
class Options:
    out: Path
    width: int
    wallpapers: Path
    nixos: Path
    after_dir: Path | None  # compare <after_dir>/<slug>.svg instead of build/16x9.svg

    @property
    def cache(self) -> Path:
        return self.out / ".cache"


def shown(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def review(slug: str, opts: Options) -> Piece:
    """Everything one card needs; image files are written under opts.out."""
    folder = opts.wallpapers / slug
    build = folder / "build"
    piece = Piece(slug)
    try:
        meta, piece.copy = meta_copy(folder)
        original = original_of(slug, opts.nixos)
        after_path = opts.after_dir / f"{slug}.svg" if opts.after_dir else build / "16x9.svg"
        if original is None:
            piece.status, piece.note = "no-original", "no nixos SVG with this name"
        elif not after_path.exists():
            piece.status, piece.note = "not-built", f"{shown(after_path)} is missing"
        before = after = None
        if original is not None:
            before = rasterise(original.read_text(), opts.width, opts.cache)
            piece.before = save(before, opts.out, f"img/{slug}/before.webp")
            piece.before_svg = original.as_uri()
        if after_path.exists():
            after = rasterise(after_path.read_text(), opts.width, opts.cache)
            piece.after = save(after, opts.out, f"img/{slug}/after.webp")
            piece.after_svg = after_path.resolve().as_uri()
        if before is not None and after is not None:
            piece.score, piece.mad, piece.ssim, diff = compare(before, after)
            piece.diff = save(diff, opts.out, f"img/{slug}/diff.webp")
        small = opts.width // 2
        light = light_svg(build)
        if light is not None:
            img = thumb(rasterise(light[0], opts.width, opts.cache), small)
            piece.light, piece.light_note = save(img, opts.out, f"img/{slug}/light.webp"), light[1]
        piece.legacy = (folder / "source.svg").exists() and not (folder / "design.py").exists()
        for aspect, file in native_templates(build):
            piece.native.append(aspect)
            if aspect == "16:9" or not (build / file).exists():
                continue
            svg = (build / file).read_text()
            w, h = viewbox(svg)
            img = rasterise(svg, round(STRIP * w / h), opts.cache)
            name = aspect.replace(":", "x")
            rel = save(img, opts.out, f"img/{slug}/a-{name}.webp")
            piece.aspects.append({"aspect": aspect, "img": rel})
        labels = meta.get("variants")
        # meta.yaml order, as on the site; a build/ directory it does not list is stale.
        for name, info in labels.items() if isinstance(labels, dict) else ():
            template = build / str(name) / "16x9.svg"
            if name == "default" or not template.exists():
                continue
            info = info if isinstance(info, dict) else {}
            img = thumb(rasterise(template.read_text(), opts.width, opts.cache), small)
            piece.variants.append(
                {
                    "name": str(name),
                    "label": str(info.get("label", "")),
                    "draft": "draft" if info.get("draft") else "",
                    "img": save(img, opts.out, f"img/{slug}/v-{name}.webp"),
                }
            )
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        piece.status, piece.note = "error", f"{type(exc).__name__}: {exc}"
    return piece


def order(pieces: list[Piece]) -> list[Piece]:
    """Compared pieces by score, then mean difference, highest first; the rest after, by slug."""
    rank = {"compared": 0, "error": 1, "not-built": 2, "no-original": 3}
    return sorted(pieces, key=lambda p: (rank[p.status], -p.score, -p.mad, p.slug))


CSS = """
:root { color-scheme: dark light; --bg: #1b1b1b; --fg: #e6e4dc; --dim: #a09e96; --rule: #3a3936;
  --mark: #e08a6e; }
@media (prefers-color-scheme: light) {
  :root { --bg: #fbfaf6; --fg: #1d1c1a; --dim: #5d5b56; --rule: #d6d3ca; --mark: #a8452a; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.45 system-ui, sans-serif; }
header, main, .twins { max-width: 1500px; margin: 0 auto; padding: 16px; }
.twins h2 { font-size: 20px; }
header p { color: var(--dim); margin: 4px 0; }
.controls { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-top: 8px; }
input, select { font: inherit; background: transparent; color: inherit;
  border: 1px solid var(--rule); padding: 4px 8px; }
article { border-top: 1px solid var(--rule); padding: 16px 0 20px; scroll-margin-top: 8px; }
article:focus { outline: 2px solid var(--mark); outline-offset: 4px; }
h2 { font-size: 18px; margin: 0 0 4px; }
h2 .rank { color: var(--dim); font-weight: normal; margin-right: 8px; }
.metrics { font-family: ui-monospace, monospace; font-size: 13px; color: var(--dim); }
.metrics b { color: var(--fg); }
.row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
.row.small { grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
figure { margin: 0; }
figure img { width: 100%; height: auto; display: block; outline: 1px solid var(--rule); }
figcaption { font-size: 13px; color: var(--dim); margin-top: 2px; }
.copy { margin-top: 10px; max-width: 80ch; }
.copy dt { color: var(--dim); font-size: 13px; margin-top: 6px; }
.copy dd { margin: 0; }
.note { color: var(--mark); }
.hidden { display: none; }
.strip { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; align-items: flex-end; }
.strip figure img { height: 150px; width: auto; }
.lists details { border-top: 1px solid var(--rule); padding: 8px 0; }
.lists summary { cursor: pointer; font-weight: 600; }
.lists ul { margin: 6px 0; padding-left: 20px; columns: 2 28em; }
.lists li { break-inside: avoid; margin-bottom: 2px; }
.twin { border-top: 1px solid var(--rule); padding: 12px 0; }
.twin h3 { font-size: 16px; margin: 0 0 4px; }
.stats { font-family: ui-monospace, monospace; font-size: 13px; }
@media (max-width: 700px) { .row { grid-template-columns: 1fr; } }
"""

SCRIPT = """
const cards = () => [...document.querySelectorAll("article:not(.hidden)")];
function move(step) {
  const list = cards();
  const at = list.indexOf(document.activeElement);
  const next = list[Math.max(0, Math.min(list.length - 1, at + step))];
  if (next) { next.focus(); next.scrollIntoView({block: "start"}); }
}
document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, select") || e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === "j") move(1);
  else if (e.key === "k") move(-1);
  else if (e.key === "/") { e.preventDefault(); document.getElementById("filter").focus(); }
  else return;
  e.preventDefault();
});
const main = document.querySelector("main");
document.getElementById("sort").addEventListener("change", (e) => {
  const key = e.target.value;
  const list = [...main.children];
  const value = (a) => key === "slug" ? a.id : Number(a.dataset[key]);
  list.sort((a, b) => key === "slug" ? value(a).localeCompare(value(b))
    : key === "ssim" ? value(a) - value(b) : value(b) - value(a));
  list.forEach((a) => main.appendChild(a));
});
document.getElementById("filter").addEventListener("input", (e) => {
  const q = e.target.value.trim().toLowerCase();
  for (const a of main.children) a.classList.toggle("hidden", q !== "" && !a.dataset.text.includes(q));
});
"""


def figure(src: str, caption: str, link: str = "") -> str:
    if not src:
        return f"<figure><figcaption>{html.escape(caption)}: none</figcaption></figure>"
    img = f'<img src="{html.escape(src)}" alt="{html.escape(caption)}" loading="lazy">'
    if link:
        img = f'<a href="{html.escape(link)}">{img}</a>'
    return f"<figure>{img}<figcaption>{html.escape(caption)}</figcaption></figure>"


def copy_html(copy: dict[str, object]) -> str:
    rows = []
    for key, label in (
        ("title", "Title"),
        ("description", "Description"),
        ("docstring", "Docstring"),
        ("notes", "Notes"),
    ):
        if copy.get(key):
            rows.append(f"<dt>{label}</dt><dd>{html.escape(str(copy[key]))}</dd>")
    variants = copy.get("variants")
    if isinstance(variants, dict):
        items = []
        for name, info in variants.items():
            info = info if isinstance(info, dict) else {}
            text = f"{name}: {info.get('label', '')}"
            if info.get("description"):
                text += f" ({info['description']})"
            if info.get("draft"):
                text += " [draft]"
            items.append(html.escape(text))
        rows.append(f"<dt>Versions</dt><dd>{'<br>'.join(items)}</dd>")
    sources = copy.get("sources")
    if isinstance(sources, list) and sources:
        items = []
        for src in sources:
            if isinstance(src, dict):
                bits = [str(src.get(k)) for k in ("kind", "title", "author", "year") if src.get(k)]
                text = html.escape(", ".join(bits))
                if src.get("url"):
                    url = html.escape(str(src["url"]))
                    text += f' <a href="{url}">{url}</a>'
                items.append(text)
        rows.append(f"<dt>Sources</dt><dd>{'<br>'.join(items)}</dd>")
    licence = copy.get("license")
    franchise = copy.get("franchise")
    if licence or franchise:
        text = str(licence or "")
        if isinstance(franchise, dict):
            text += f" ({franchise.get('title', '')}, {franchise.get('owner', '')})"
        rows.append(f"<dt>Licence</dt><dd>{html.escape(text)}</dd>")
    return f'<dl class="copy">{"".join(rows)}</dl>' if rows else ""


def card(rank: int, p: Piece) -> str:
    title = str(p.copy.get("title", ""))
    text = " ".join([p.slug, title, str(p.copy.get("description", ""))]).lower()
    head = (
        f'<h2><span class="rank">{rank}</span>{html.escape(p.slug)}'
        + (f" · {html.escape(title)}" if title else "")
        + (" · draft" if p.copy.get("draft") else "")
        + "</h2>"
    )
    if p.status == "compared":
        metrics = (
            f'<div class="metrics">changed <b>{p.score:.2f}%</b> · mean diff {p.mad:.2f}'
            f" · SSIM {p.ssim:.4f}</div>"
        )
    else:
        metrics = f'<div class="metrics note">{html.escape(p.status)}: {html.escape(p.note)}</div>'
    pair = (
        '<div class="row">'
        + figure(p.before, "nixos original", p.before_svg)
        + figure(p.after, "new 16:9 template", p.after_svg)
        + figure(p.diff, "difference: white where changed")
        + "</div>"
    )
    small = []
    if p.light:
        small.append(figure(p.light, p.light_note))
    for v in p.variants:
        caption = f"version {v['name']}" + (f": {v['label']}" if v["label"] else "")
        small.append(figure(v["img"], caption + (f" ({v['draft']})" if v["draft"] else "")))
    extra = f'<div class="row small">{"".join(small)}</div>' if small else ""
    if p.aspects:
        shapes = "".join(figure(a["img"], a["aspect"]) for a in p.aspects)
        extra += f'<div class="strip">{shapes}</div>'
    if p.native:
        extra += f'<div class="metrics">native: {html.escape(", ".join(p.native))}</div>'
    attrs = (
        f'id="{html.escape(p.slug)}" tabindex="0" data-score="{p.score}" data-mad="{p.mad}"'
        f' data-ssim="{p.ssim}" data-text="{html.escape(text)}"'
    )
    return f"<article {attrs}>{head}{metrics}{pair}{extra}{copy_html(p.copy)}</article>"


def sources_of(p: Piece, kind: str) -> list[dict[str, object]]:
    sources = p.copy.get("sources")
    items = sources if isinstance(sources, list) else []
    return [s for s in items if isinstance(s, dict) and s.get("kind") == kind]


def credit(src: dict[str, object]) -> str:
    return ", ".join(str(src[k]) for k in ("author", "title", "year") if src.get(k))


def licence(p: Piece) -> str:
    return str(p.copy.get("license") or "CC0-1.0 (default)")


def entry(p: Piece, **extra: object) -> dict[str, object]:
    return {"slug": p.slug, "title": str(p.copy.get("title", "")), **extra}


def lists(pieces: list[Piece]) -> dict[str, list[dict[str, object]]]:
    """The review's lists, each sorted by slug: draft pieces, draft versions, recreations with
    their licence, fan pieces, pieces kept at 16:9, pieces with some but not all aspects, and
    legacy pieces."""
    out: dict[str, list[dict[str, object]]] = {
        k: []
        for k in (
            "draft_pieces",
            "draft_versions",
            "recreations",
            "fan_pieces",
            "kept_16x9",
            "some_aspects",
            "legacy",
        )
    }
    for p in sorted(pieces, key=lambda p: p.slug):
        if p.copy.get("draft"):
            out["draft_pieces"].append(entry(p))
        variants = p.copy.get("variants")
        for name, info in variants.items() if isinstance(variants, dict) else ():
            if name != "default" and isinstance(info, dict) and info.get("draft"):
                out["draft_versions"].append(entry(p, name=name, label=info.get("label", "")))
        if made := sources_of(p, "recreation"):
            out["recreations"].append(entry(p, license=licence(p), after=[credit(s) for s in made]))
        if p.copy.get("license") == "LicenseRef-fan-work":
            franchise = p.copy.get("franchise")
            f = franchise if isinstance(franchise, dict) else {}
            out["fan_pieces"].append(
                entry(p, franchise=f.get("title", ""), owner=f.get("owner", ""))
            )
        if p.native == ["16:9"]:
            out["kept_16x9"].append(entry(p, legacy=p.legacy))
        elif p.native and len(p.native) < len(SITE_ASPECTS):
            out["some_aspects"].append(entry(p, aspects=p.native))
        if p.legacy:
            out["legacy"].append(entry(p))
    return out


def twins(pieces: list[Piece], opts: Options) -> list[dict[str, object]]:
    """Each `<slug>-branch` with its `<slug>` twin: both drafts flags and the share of pixels
    that differ between their 16:9 templates (None when either is not built)."""
    by_slug = {p.slug: p for p in pieces}
    out: list[dict[str, object]] = []
    for p in sorted(pieces, key=lambda p: p.slug):
        base = by_slug.get(p.slug.removesuffix("-branch"))
        if not p.slug.endswith("-branch") or base is None:
            continue
        score = None
        paths = [opts.wallpapers / s / "build" / "16x9.svg" for s in (base.slug, p.slug)]
        if all(path.exists() for path in paths):
            a, b = (rasterise(path.read_text(), opts.width, opts.cache) for path in paths)
            score = compare(a, b)[0]
        out.append(
            {
                "base": base.slug,
                "branch": p.slug,
                "score": score,
                "base_draft": bool(base.copy.get("draft")),
                "branch_draft": bool(p.copy.get("draft")),
            }
        )
    return out


def anchor(item: dict[str, object]) -> str:
    slug = html.escape(str(item["slug"]))
    title = html.escape(str(item.get("title", "")))
    return f'<a href="#{slug}">{slug}</a>' + (f" · {title}" if title else "")


def joined(value: object, sep: str) -> str:
    return sep.join(map(str, value)) if isinstance(value, list) else str(value)


type Item = dict[str, object]

LISTS: dict[str, tuple[str, Callable[[Item], str]]] = {
    "draft_pieces": ("Draft pieces", lambda i: ""),
    "draft_versions": ("Draft versions", lambda i: f": {i['name']} ({i['label']})"),
    "recreations": (
        "Recreations and their licence",
        lambda i: f": {i['license']}, after {joined(i['after'], '; ')}",
    ),
    "fan_pieces": ("Fan pieces", lambda i: f": {i['franchise']} ({i['owner']})"),
    "kept_16x9": ("Kept at 16:9", lambda i: " (legacy)" if i.get("legacy") else ""),
    "some_aspects": ("Some aspects only", lambda i: f": {joined(i['aspects'], ', ')}"),
}


def lists_html(data: dict[str, list[dict[str, object]]]) -> str:
    parts = []
    for key, (title, detail) in LISTS.items():
        items = data[key]
        rows = "".join(f"<li>{anchor(i)}{html.escape(detail(i))}</li>" for i in items)
        parts.append(f"<details><summary>{title} ({len(items)})</summary><ul>{rows}</ul></details>")
    return f'<section class="lists">{"".join(parts)}</section>'


def twins_html(pairs: list[dict[str, object]], by_slug: dict[str, Piece]) -> str:
    if not pairs:
        return ""
    parts = []
    for t in pairs:
        base, branch = by_slug[str(t["base"])], by_slug[str(t["branch"])]
        score = "not built" if t["score"] is None else f"{t['score']:.2f}% of pixels differ at 16:9"
        flag = {True: " (draft)", False: " (published)"}
        head = (
            f'<h3><a href="#{html.escape(base.slug)}">{html.escape(base.slug)}</a>{flag[base.copy.get("draft") is True]}'
            f' and <a href="#{html.escape(branch.slug)}">{html.escape(branch.slug)}</a>'
            f"{flag[branch.copy.get('draft') is True]} · {score}</h3>"
        )
        row = (
            '<div class="row">'
            + figure(base.before, "nixos original", base.before_svg)
            + figure(base.after, f"{base.slug} 16:9", base.after_svg)
            + figure(branch.after, f"{branch.slug} 16:9", branch.after_svg)
            + "</div>"
        )
        strips = ""
        for p in (base, branch):
            shapes = "".join(figure(a["img"], f"{p.slug} {a['aspect']}") for a in p.aspects)
            strips += f'<div class="strip">{shapes}</div>' if shapes else ""
        parts.append(
            f'<article class="twin" id="twin-{html.escape(base.slug)}">{head}{row}{strips}</article>'
        )
    return (
        '<section class="twins"><h2>Twins: the nixos import and the branch rewrite</h2>'
        "<p>Review keeps one of each pair; the other is dropped, and a kept -branch folder is"
        " renamed.</p>" + "".join(parts) + "</section>"
    )


def stats(pieces: list[Piece], data: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    """Counts for the page header and summary.json."""
    compared = [p for p in pieces if p.status == "compared"]
    buckets = {"0%": 0, "under 1%": 0, "1-5%": 0, "5-20%": 0, "20% and over": 0}
    for p in compared:
        key = (
            "0%" if p.score == 0 else "under 1%" if p.score < 1 else "1-5%" if p.score < 5
            else "5-20%" if p.score < 20 else "20% and over"
        )  # fmt: skip
        buckets[key] += 1
    statuses: dict[str, int] = {}
    for p in pieces:
        statuses[p.status] = statuses.get(p.status, 0) + 1
    return {
        "pieces": len(pieces),
        "published": sum(1 for p in pieces if not p.copy.get("draft")),
        "statuses": statuses,
        "changed_pixels": buckets,
        "every_aspect": sum(1 for p in pieces if len(p.native) == len(SITE_ASPECTS)),
        **{k: len(v) for k, v in data.items()},
    }


def page(pieces: list[Piece], width: int, pairs: list[dict[str, object]] | None = None) -> str:
    data = lists(pieces)
    s = stats(pieces, data)
    statuses = s["statuses"]
    summary = (
        ", ".join(f"{n} {k}" for k, n in statuses.items()) if isinstance(statuses, dict) else ""
    )
    buckets = s["changed_pixels"]
    spread = ", ".join(f"{n} {k}" for k, n in buckets.items()) if isinstance(buckets, dict) else ""
    facts = (
        f'<p class="stats">{s["published"]} published, {s["draft_pieces"]} draft pieces,'
        f" {s['draft_versions']} draft versions; {s['every_aspect']} at every aspect,"
        f" {s['some_aspects']} at some, {s['kept_16x9']} at 16:9 only; {s['recreations']}"
        f" recreations, {s['fan_pieces']} fan pieces, {s['legacy']} legacy.<br>Changed pixels at"
        f" 16:9: {html.escape(spread)}.</p>"
    )
    by_slug = {p.slug: p for p in pieces}
    cards = "\n".join(card(i, p) for i, p in enumerate(pieces, 1))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Port review</title>
<style>{CSS}</style>
</head>
<body>
<header>
<h1>Port review</h1>
<p>{len(pieces)} pieces: {html.escape(summary)}. Rendered {width} px wide; changed = pixels
whose largest channel difference exceeds {THRESHOLD}. Generated {datetime.now(UTC).astimezone():%Y-%m-%d %H:%M}.</p>
<p>j and k move between pieces, / filters. Each image links to its SVG.</p>
{facts}
<div class="controls">
<label>Sort <select id="sort">
<option value="score">changed pixels</option>
<option value="mad">mean difference</option>
<option value="ssim">SSIM, lowest first</option>
<option value="slug">slug</option>
</select></label>
<label>Filter <input id="filter" type="search" placeholder="slug or title"></label>
</div>
{lists_html(data)}
</header>
{twins_html(pairs or [], by_slug)}
<main>
{cards}
</main>
<script>{SCRIPT}</script>
</body>
</html>
"""


def slugs_to_review(args: argparse.Namespace) -> list[str]:
    if args.slugs:
        return list(args.slugs)
    if args.after_dir:
        return sorted(p.stem for p in args.after_dir.glob("*.svg"))
    return sorted(p.name for p in args.wallpapers.iterdir() if (p / "meta.yaml").exists())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("slugs", nargs="*", help="pieces to review (default: all)")
    parser.add_argument("--nixos", type=Path, default=NIXOS, help="the nixos backgrounds")
    parser.add_argument("--wallpapers", type=Path, default=ROOT / "wallpapers")
    parser.add_argument("--after-dir", type=Path, help="compare DIR/<slug>.svg instead of build/")
    parser.add_argument("--out", type=Path, default=ROOT / "import" / "review")
    parser.add_argument("--width", type=int, default=960, help="raster width of the pairs")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    slugs = slugs_to_review(args)
    if not slugs:
        sys.exit("nothing to review")
    opts = Options(args.out, args.width, args.wallpapers, args.nixos, args.after_dir)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.jobs == 1:
        pieces = [review(slug, opts) for slug in slugs]
    else:
        with ProcessPoolExecutor(args.jobs) as pool:
            pieces = list(pool.map(review, slugs, [opts] * len(slugs)))
    pieces = order(pieces)
    pairs = twins(pieces, opts)
    (args.out / "index.html").write_text(page(pieces, args.width, pairs))
    data = lists(pieces)
    summary = {
        "generated": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
        "width": args.width,
        "threshold": THRESHOLD,
        "stats": stats(pieces, data),
        "lists": data,
        "twins": pairs,
        "pieces": [asdict(p) for p in pieces],
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(args.out / "index.html")
    for p in pieces:
        detail = f"{p.score:6.2f}% ssim {p.ssim:.4f}" if p.status == "compared" else p.note
        print(f"{p.slug}: {p.status} {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

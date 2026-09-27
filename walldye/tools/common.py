"""Shared helpers for the walldye tools: repo layout, metadata, rendering and rasterising."""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import re
import sys
from pathlib import Path

import numpy as np
import resvg_py
import yaml
from PIL import Image

import walldye
from walldye._theme import normalise_seed
from walldye.tools.tokenize import find_colours, substitute

sys.dont_write_bytecode = True  # exec'd designs must not leave __pycache__ in wallpapers/<slug>/

# The package is only used from a checkout (editable install), so the repo is two levels up.
ROOT = Path(__file__).resolve().parents[2]
WALLPAPERS = ROOT / "wallpapers"
TAXONOMY = ROOT / "taxonomy.yaml"
DEFAULT_ASPECTS = ["16:9"]
Crop = tuple[float, float, float, float]
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def piece_dir(slug: str) -> Path:
    """wallpapers/<slug>/, whether or not it exists; ValueError unless `slug` is lowercase words joined by single hyphens."""
    if not _SLUG.fullmatch(slug):
        raise ValueError(f"bad slug {slug!r} (lowercase letters and digits, single hyphens)")
    return WALLPAPERS / slug


def build_dir(slug: str) -> Path:
    return piece_dir(slug) / "build"


def slugs() -> list[str]:
    """Sorted slugs of every wallpapers/<slug>/ holding a meta.yaml."""
    return sorted(p.parent.name for p in WALLPAPERS.glob("*/meta.yaml"))


def is_legacy(slug: str) -> bool:
    """True for a script-less piece (source.svg + palette.yaml); FileNotFoundError if it is neither kind."""
    d = piece_dir(slug)
    if (d / "design.py").exists():
        return False
    if (d / "source.svg").exists():
        return True
    raise FileNotFoundError(f"{d} has neither design.py nor source.svg")


def load_meta(slug: str) -> dict:
    """Parsed wallpapers/<slug>/meta.yaml ({} when empty; dates come back as datetime.date).
    ValueError naming the file when it is not valid YAML or not a mapping."""
    path = piece_dir(slug) / "meta.yaml"
    try:
        meta = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark else ""
        raise ValueError(
            f"{path}: not valid YAML{where}: {getattr(e, 'problem', None) or e}"
        ) from e
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: must be a mapping")
    return meta


def is_draft(meta: dict) -> bool:
    """Whether meta.yaml `meta` marks its piece a draft: only `draft: true` does."""
    return meta.get("draft") is True


def is_aspect(value: str) -> bool:
    """Whether `value` names an aspect walldye.canvas_size() turns into a positive canvas ('16:9', '3440x1440')."""
    try:
        w, h = walldye.canvas_size(value)
    except (ValueError, ZeroDivisionError, OverflowError):
        return False
    return w > 0 and h > 0


def design_aspects(slug: str) -> list[str]:
    """The ASPECTS list a design declares, read statically from design.py; DEFAULT_ASPECTS when
    it declares none and for legacy pieces. ValueError naming design.py unless ASPECTS is a
    literal list of strings, each "any" or an aspect (is_aspect); SyntaxError propagates."""
    if is_legacy(slug):
        return list(DEFAULT_ASPECTS)
    path = piece_dir(slug) / "design.py"
    for node in ast.parse(path.read_text(), str(path)).body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value:
            targets = [node.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == "ASPECTS" for t in targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                value = None
            if not isinstance(value, (list, tuple)) or not all(isinstance(a, str) for a in value):
                raise ValueError(
                    f'{path}: ASPECTS must be a literal list of strings, like ["any"] or ["16:9", "21:9"]'
                )
            for a in value:
                if a != "any" and not is_aspect(a):
                    raise ValueError(
                        f'{path}: ASPECTS entry {a!r} is not "any" or an aspect like 16:9'
                    )
            return list(value)
    return list(DEFAULT_ASPECTS)


def render(slug: str, theme: str | dict[str, str] | None = None, aspect: str = "16:9") -> str:
    """SVG text of one piece under `theme` (theme token or {bg, fg, accent}) at `aspect`.

    Runs set_theme(), then set_canvas(), then execs design.py fresh as module `_walldye_<slug>`
    (never adding its directory to sys.path) and calls draw(); walldye.pixel_grids() then
    describes this render; the design's print() output goes to stderr. A legacy piece is
    source.svg with every slot (tokenize.find_colours) whose colour palette.yaml lists replaced by
    its token value under `theme`; it only exists at 16:9 (ValueError otherwise). Errors from the
    design propagate unchanged.
    """
    d = piece_dir(slug)
    walldye.set_theme(theme)
    walldye.set_canvas(aspect)
    if is_legacy(slug):
        return _render_legacy(d, aspect)
    name = f"_walldye_{slug}"
    spec = importlib.util.spec_from_file_location(name, d / "design.py")
    mod = importlib.util.module_from_spec(spec)
    # Registered while it runs: dataclasses and friends look their module up in sys.modules.
    sys.modules[name] = mod
    try:
        # stdout carries `render -o -` output and the _hashes JSON.
        with contextlib.redirect_stdout(sys.stderr):
            spec.loader.exec_module(mod)
            s = walldye.Svg(bg=getattr(mod, "BG", walldye.THEME["bg"]))
            mod.draw(s)
    finally:
        sys.modules.pop(name, None)
    return s.to_string()


def _render_legacy(d: Path, aspect: str) -> str:
    if walldye.canvas_size(aspect) != walldye.canvas_size("16:9"):
        raise ValueError(f"{d.name} is a legacy piece and only exists at 16:9, not {aspect}")
    # palette.yaml: "#RRGGBB": token, or "#RRGGBB": [token_a, token_b, t] for mix(a, b, t).
    palette = yaml.safe_load((d / "palette.yaml").read_text()) or {}
    theme = walldye.THEME
    try:
        values = {
            normalise_seed(c): theme[v]
            if isinstance(v, str)
            else walldye.mix(theme[v[0]], theme[v[1]], v[2])
            for c, v in palette.items()
        }
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(
            f"{d / 'palette.yaml'}: entries must be a token or [token, token, t] ({e!r})"
        ) from e
    source = (d / "source.svg").read_text()
    return substitute(
        source, [values.get(c, source[start:end]) for start, end, c in find_colours(source)]
    )


def viewbox(svg: str) -> str | None:
    """The root <svg> element's viewBox value, or None when it has none."""
    root = re.search(r"<svg\b[^>]*>", svg)
    m = root and re.search(r'\sviewBox\s*=\s*"([^"]*)"', root.group(0))
    return m.group(1) if m else None


def crop_svg(svg: str, crop: Crop) -> str:
    """`svg` cut to the canvas box `crop` (x, y, w, h): the root viewBox becomes the box, width/height its size."""
    x, y, w, h = crop
    svg = re.sub(r'viewBox="[^"]*"', f'viewBox="{x:g} {y:g} {w:g} {h:g}"', svg, count=1)
    return re.sub(
        r'(<svg[^>]*?) width="[^"]*" height="[^"]*"',
        lambda m: f'{m.group(1)} width="{w:g}" height="{h:g}"',
        svg,
        count=1,
    )


def rasterise(svg: str, width: int, crop: Crop | None = None) -> Image.Image:
    """RGB image of `svg`, `width` px wide; the height follows the viewBox (or `crop`) aspect.

    `crop` is applied with crop_svg(). resvg's ValueError on invalid SVG propagates.
    """
    if crop:
        svg = crop_svg(svg, crop)
        _, _, w, h = crop
    else:
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        w, h = (float(m.group(1)), float(m.group(2))) if m else (16, 9)
    data = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width, height=round(width * h / w)))
    # resvg emits RGBA; wallpapers are opaque, and some setters dislike alpha.
    return Image.open(io.BytesIO(data)).convert("RGB")


def _ink(img: Image.Image, bg: str) -> np.ndarray:
    return np.linalg.norm(np.asarray(img, float) - np.array(walldye.hex_to_rgb(bg), float), axis=2)


def ink_map(img: Image.Image, bg: str, size: tuple[int, int] = (64, 36)) -> np.ndarray:
    """Per-pixel RGB distance from `bg` at `size`, flattened to a unit vector (all zeros when blank):
    what a design 'looks like'. The dot product of two maps is their cosine similarity."""
    d = _ink(img.resize(size), bg)
    n = np.linalg.norm(d)
    return d.ravel() / n if n else d.ravel()


def focus(img: Image.Image, bg: str) -> tuple[float, float]:
    """Ink-weighted centroid of `img` (weights = RGB distance from `bg`) as (x, y) fractions of its
    width and height, rounded to 4 dp; (0.5, 0.5) when nothing differs from `bg`."""
    d = _ink(img, bg)
    total = d.sum()
    if not total:
        return 0.5, 0.5
    h, w = d.shape
    fx = (d.sum(axis=0) * (np.arange(w) + 0.5)).sum() / total / w
    fy = (d.sum(axis=1) * (np.arange(h) + 0.5)).sum() / total / h
    return round(float(fx), 4), round(float(fy), 4)

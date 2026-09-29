"""Shared helpers for the walldye tools: repo layout, metadata, loading and drawing designs,
serializing and rasterizing."""

import contextlib
import hashlib
import importlib.util
import io
import itertools
import os
import re
import shutil
import sys
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, cast, final

import numpy as np
import resvg_py
import yaml
from numpy.typing import NDArray
from PIL import Image

from walldye._aspect import Aspect, canvas_size
from walldye._color import Color, mix, token
from walldye._design import Design, RenderSpec
from walldye._document import Document
from walldye._params import Params
from walldye._theme import (
    PRESETS,
    SEEDS,
    hex_to_rgb,
    is_light,
    normalize_seed,
    parse_seeds,
    theme_tokens,
)
from walldye.tools import knobs
from walldye.tools.tokenize import find_colors

sys.dont_write_bytecode = True  # imported designs must not leave __pycache__ in wallpapers/<slug>/

# An editable install sits in a checkout two levels up; an installed package (the Nix one) is
# pointed at a folder holding wallpapers/ and taxonomy.yaml by $WALLDYE_ROOT.
_ROOT_ENV: Final = os.environ.get("WALLDYE_ROOT", "")
ROOT: Final = Path(_ROOT_ENV) if _ROOT_ENV != "" else Path(__file__).resolve().parents[2]
WALLPAPERS = ROOT / "wallpapers"
TAXONOMY = ROOT / "taxonomy.yaml"
DESIGN_PYREFLY: Final = ROOT / "wallpapers" / "pyrefly.toml"  # the level designs are checked at
DESIGN_ERROR: Final = "design.py must define @design(...) def draw(s: Canvas[...]) -> None"
FIREPROOF_BG: Final = PRESETS["fireproof"]["bg"]
DOC_CACHE: Final = 16
FOCUS_WIDTH: Final = 480  # px wide the focus is measured at

type Crop = tuple[float, float, float, float]
type Regime = Literal["dark", "light"]
REGIMES: Final[tuple[Regime, ...]] = ("dark", "light")
type Meta = dict[str, object]
type Theme = str | Mapping[str, str] | tuple[str, str, str]
_SLUG: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_BACKGROUND: Final = re.compile(
    r"<svg\b[^\n]*\n(?:<defs>[^\n]*</defs>\n)?"
    r'<rect x="0" y="0" width="\d+" height="\d+" fill="(#[0-9A-Fa-f]{6})"/>\n'
)


class UsageError(Exception):
    """A command-line mistake the CLI reports with exit code 2."""


def tool(name: str) -> Path | None:
    """The dev tool `name` (ruff, pyrefly) of walldye's environment: next to sys.executable,
    else on PATH (under `uv run --with`, sys.executable is an overlay environment without the
    project's tools, and uv puts the project's .venv/bin on PATH). None when neither has it."""
    beside = Path(sys.executable).with_name(name)
    if beside.exists():
        return beside
    found = shutil.which(name)
    return None if found is None else Path(found)


def piece_dir(slug: str) -> Path:
    """wallpapers/<slug>/, whether or not it exists; ValueError unless `slug` is lowercase
    words joined by single hyphens."""
    if _SLUG.fullmatch(slug) is None:
        raise ValueError(f"bad slug {slug!r} (lowercase letters and digits, single hyphens)")
    return WALLPAPERS / slug


def build_dir(slug: str, variant: str = "default") -> Path:
    """build/ for the default variant, build/<variant>/ for a named one."""
    b = piece_dir(slug) / "build"
    return b if variant == "default" else b / variant


def slugs() -> list[str]:
    """Sorted slugs of every wallpapers/<slug>/ holding a meta.yaml."""
    return sorted(p.parent.name for p in WALLPAPERS.glob("*/meta.yaml"))


def is_legacy(slug: str) -> bool:
    """True for a script-less piece (source.svg + palette.yaml); FileNotFoundError if it is
    neither kind."""
    d = piece_dir(slug)
    if (d / "design.py").exists():
        return False
    if (d / "source.svg").exists():
        return True
    raise FileNotFoundError(f"{d} has neither design.py nor source.svg")


def as_dict(value: object) -> dict[str, object] | None:
    """`value` as a dict with str keys (a parsed YAML or JSON mapping), else None."""
    if not isinstance(value, dict):
        return None
    items = cast("dict[object, object]", value).items()
    return {str(k): v for k, v in items}


def as_list(value: object) -> list[object] | None:
    """`value` as a list (a parsed YAML or JSON sequence), else None."""
    return cast("list[object]", value) if isinstance(value, list) else None


def load_meta(slug: str) -> Meta:
    """Parsed wallpapers/<slug>/meta.yaml ({} when empty; dates come back as datetime.date).
    ValueError naming the file when it is not valid YAML or not a mapping."""
    path = piece_dir(slug) / "meta.yaml"
    try:
        data: object = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        where, problem = "", str(e)
        if isinstance(e, yaml.MarkedYAMLError):
            where = "" if e.problem_mark is None else f" (line {e.problem_mark.line + 1})"
            if e.problem is not None:
                problem = e.problem
        raise ValueError(f"{path}: not valid YAML{where}: {problem}") from e
    if data is None:
        return {}
    meta = as_dict(data)
    if meta is None:
        raise ValueError(f"{path}: must be a mapping")
    return meta


def is_draft(meta: Meta) -> bool:
    """Whether meta.yaml `meta` marks its piece a draft: only `draft: true` does."""
    return meta.get("draft") is True


def meta_variants(meta: Meta) -> dict[str, dict[str, object]]:
    """meta.yaml `variants:` as {name: entry}, in file order; malformed entries are left out
    (lint.meta reports them)."""
    out: dict[str, dict[str, object]] = {}
    variants = as_dict(meta.get("variants"))
    if variants is None:
        return out
    for name, entry in variants.items():
        if (e := as_dict(entry)) is not None:
            out[name] = e
    return out


def is_aspect(value: str) -> bool:
    """Whether `value` names an aspect canvas_size() accepts ('16:9', '3440x1440')."""
    try:
        w, h = canvas_size(value)
    except (ValueError, ZeroDivisionError, OverflowError):
        return False
    return w > 0 and h > 0


def seeds_of(theme: Theme) -> dict[str, str]:
    """{bg, fg, accent} of a theme token, a seed mapping or a (bg, fg, accent) triple."""
    if isinstance(theme, str):
        return parse_seeds(theme)
    if isinstance(theme, tuple):
        return dict(zip(SEEDS, theme, strict=True))
    return {k: normalize_seed(theme[k]) for k in SEEDS}


def tokens_of(theme: Theme) -> dict[str, str]:
    """The 21 tokens of a theme token, seed mapping or seed triple."""
    return theme_tokens(seeds_of(theme))


def regime_of(theme: Theme) -> Regime:
    """The regime a theme's seeds select."""
    s = seeds_of(theme)
    return "light" if is_light(s["bg"], s["fg"]) else "dark"


@final
class LegacyPiece:
    """A script-less piece: source.svg with every color mapped to a token or a two-token mix
    by palette.yaml. It has only the default variant, at 16:9, and draws one document for
    both regimes."""

    declared_aspects: Final[tuple[Aspect, ...]] = ("16:9",)
    aspects: Final[tuple[Aspect, ...]] = ("16:9",)
    params_type: Final = Params

    def __init__(self, source: Path) -> None:
        """Cut source.svg at its slots and map each through palette.yaml, a mapping of hex to
        a token name or [token, token, t] for mix(). ValueError naming palette.yaml for a
        malformed entry or a color it does not map."""
        self.source: Final = source
        self.variants: Final[Mapping[str, Params]] = MappingProxyType({})
        palette_path = source.with_name("palette.yaml")
        entries = as_dict(yaml.safe_load(palette_path.read_text()) or {})
        if entries is None:
            raise ValueError(f"{palette_path}: must map colors to tokens")
        palette: dict[str, Color] = {}
        for hex_, value in entries.items():
            try:
                palette[normalize_seed(hex_)] = _palette_color(value)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"{palette_path}: {hex_}: entries are a token or [token, token, t] ({e})"
                ) from e
        text = source.read_text()
        parts: list[str] = []
        colors: list[Color] = []
        last = 0
        for start, end, color in find_colors(text):
            if color not in palette:
                raise ValueError(f"{palette_path} does not map {color} (used in source.svg)")
            parts.append(text[last:start])
            colors.append(palette[color])
            last = end
        parts.append(text[last:])
        self._parts: Final = tuple(parts)
        self._colors: Final = tuple(colors)

    def variant_names(self) -> tuple[str, ...]:
        """Only ("default",)."""
        return ("default",)

    def params(self, variant: str = "default") -> Params:
        """Params() for "default"; KeyError otherwise."""
        if variant != "default":
            raise KeyError(f"no variant {variant!r} (have: default)")
        return Params()

    def draw(self, spec: RenderSpec) -> Document:
        """The document of source.svg; ValueError for any aspect but 16:9."""
        if canvas_size(spec.aspect) != canvas_size("16:9"):
            raise ValueError(
                f"{self.source.parent.name} is a legacy piece and only exists at 16:9,"
                f" not {spec.aspect}"
            )
        w, h = canvas_size("16:9")
        return Document(self._parts, self._colors, w=w, h=h, regime=spec.regime)


def _palette_color(value: object) -> Color:
    if isinstance(value, str):
        return token(value)
    pair = as_list(value)
    if pair is None or len(pair) != 3:
        raise ValueError(f"not a token or [token, token, t]: {value!r}")
    a, b, t = pair
    if not isinstance(a, str) or not isinstance(b, str) or not isinstance(t, (int, float)):
        raise ValueError(f"not a token or [token, token, t]: {value!r}")
    return mix(token(a), token(b), t)


type Piece = Design[Params] | LegacyPiece

_LOADED: Final[dict[Path, tuple[str, Piece]]] = {}
_DOCS: Final[OrderedDict[tuple[Piece, RenderSpec], Document]] = OrderedDict()
_fresh = itertools.count()


def load(slug: str) -> Piece:
    """The design of wallpapers/<slug>/: its @design draw, or a LegacyPiece.

    design.py is imported once per process as module `_walldye_<slug with - as _>`, which
    stays in sys.modules; it is imported again only when the file changes. The design's
    folder is never put on sys.path, and its prints go to stderr. ValueError(DESIGN_ERROR)
    when `draw` is not a Design; import errors propagate.
    """
    d = piece_dir(slug)
    path = d / "design.py"
    if not path.exists():
        if (d / "source.svg").exists():
            return LegacyPiece(d / "source.svg")
        raise FileNotFoundError(f"{d} has neither design.py nor source.svg")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cached = _LOADED.get(path.resolve())
    if cached is not None and cached[0] == digest:
        return cached[1]
    design = _import(path, f"_walldye_{slug.replace('-', '_')}", keep=True)
    _LOADED[path.resolve()] = (digest, design)
    return design


def fresh(slug: str) -> Piece:
    """A new import of wallpapers/<slug>/design.py under a module name used once, not cached:
    for `check --paranoid`. A legacy piece is loaded as load() does."""
    path = piece_dir(slug) / "design.py"
    if not path.exists():
        return load(slug)
    return _import(path, f"_walldye_{slug.replace('-', '_')}_fresh{next(_fresh)}", keep=False)


def _import(path: Path, name: str, keep: bool) -> Design[Params]:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    # Registered while it runs: dataclasses and Params look their module up in sys.modules.
    sys.modules[name] = mod
    try:
        with contextlib.redirect_stdout(sys.stderr):
            spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    if not keep:
        sys.modules.pop(name, None)
    draw: object = getattr(mod, "draw", None)
    if not isinstance(draw, Design):
        raise ValueError(DESIGN_ERROR)
    return cast("Design[Params]", draw)


def draw(piece: Piece, spec: RenderSpec, cache: bool = True) -> Document:
    """piece.draw(spec) with the design's prints sent to stderr. With `cache`, the last
    DOC_CACHE documents are reused by (piece, spec); checks that compare draws pass False."""
    key = (piece, spec)
    doc = _DOCS.get(key) if cache else None
    if doc is not None:
        _DOCS.move_to_end(key)
        return doc
    with contextlib.redirect_stdout(sys.stderr):
        doc = piece.draw(spec)
    if cache:
        _DOCS[key] = doc
        if len(_DOCS) > DOC_CACHE:
            _DOCS.popitem(last=False)
    return doc


def variant_of(piece: Piece, slug: str, variant: str) -> str:
    """`variant` when `piece` declares it (or it is "default"); UsageError listing the names."""
    names = piece.variant_names()
    if variant not in names:
        raise UsageError(f"{slug} has no variant {variant!r} (have: {', '.join(names)})")
    return variant


def params_for(piece: Piece, variant: str, overrides: Sequence[str]) -> tuple[Params, list[str]]:
    """The params of `variant` with the `--set` items applied, and the soft-range warnings."""
    return knobs.override(piece.params(variant), overrides)


def key(slug: str, variant: str, aspect: str, regime: str) -> str:
    """The cache, file and subprocess key of one render."""
    return f"{slug}@{variant}@{aspect}@{regime}"


def render(
    slug: str,
    theme: Theme,
    aspect: str = "16:9",
    variant: str = "default",
    overrides: Sequence[str] = (),
) -> str:
    """SVG text of one piece: `variant` (with `overrides`, `--set` items) at `aspect`, drawn
    for the regime of `theme` and serialized under it. Documents are cached by spec; errors
    from the design propagate unchanged."""
    piece = load(slug)
    params, _ = params_for(piece, variant, overrides)
    doc = draw(piece, RenderSpec(variant, params, aspect, regime_of(theme)))
    return doc.to_svg(tokens_of(theme))


def viewbox(svg: str) -> str | None:
    """The root <svg> element's viewBox value, or None when it has none."""
    root = re.search(r"<svg\b[^>]*>", svg)
    m = None if root is None else re.search(r'\sviewBox\s*=\s*"([^"]*)"', root.group(0))
    return None if m is None else m.group(1)


def crop_svg(svg: str, crop: Crop) -> str:
    """`svg` cut to the canvas box `crop` (x, y, w, h): the root viewBox becomes the box,
    width/height its size."""
    x, y, w, h = crop
    svg = re.sub(r'viewBox="[^"]*"', f'viewBox="{x:g} {y:g} {w:g} {h:g}"', svg, count=1)
    return _sized(svg, w, h)


def _sized(svg: str, w: float, h: float) -> str:
    return re.sub(
        r'(<svg[^>]*?) width="[^"]*" height="[^"]*"',
        lambda m: f'{m.group(1)} width="{w:g}" height="{h:g}"',
        svg,
        count=1,
    )


def fit_crop(aspect: str, focus: tuple[float, float]) -> Crop:
    """The box of the 16:9 canvas an `aspect` it wasn't drawn for is cut from, as the site
    cuts it: the canvas's full height for a narrower aspect, else its full width, slid along
    the other axis to center on `focus` (fractions of the canvas), clamped to the canvas, the
    position rounded to 0.001."""
    cw, ch = canvas_size("16:9")
    aw, ah = canvas_size(aspect)
    ratio = aw / ah
    narrow = ratio < cw / ch
    size = ch * ratio if narrow else cw / ratio
    span = size / (cw if narrow else ch)
    f = focus[0] if narrow else focus[1]
    t = 0.5 if span >= 1 else round(min(1.0, max(0.0, (f - span / 2) / (1 - span))), 3)
    if narrow:
        return t * (cw - size), 0.0, size, float(ch)
    return 0.0, t * (ch - size), float(cw), size


def template_focus(
    slug: str, variant: str = "default", overrides: Sequence[str] = ()
) -> tuple[float, float]:
    """focus() of the piece's 16:9 dark template, the one build stores in slots.json."""
    svg = render(slug, "fireproof", "16:9", variant, overrides)
    return focus(rasterize(svg, FOCUS_WIDTH), background(svg))


def rasterize(svg: str, width: int, crop: Crop | None = None) -> Image.Image:
    """RGB image of `svg`, `width` px wide; the height follows the viewBox (or `crop`) aspect.

    `crop` is applied with crop_svg(). resvg's ValueError on invalid SVG propagates.
    """
    if crop is not None:
        svg = crop_svg(svg, crop)
        _, _, w, h = crop
    else:
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        w, h = (16.0, 9.0) if m is None else (float(m.group(1)), float(m.group(2)))
    height = round(width * h / w)
    # resvg keeps the root's width:height, and rounding that can cost a pixel of the target.
    svg = _sized(svg, width, height)
    data = resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height)
    # resvg emits RGBA; wallpapers are opaque, and some setters dislike alpha.
    return Image.open(io.BytesIO(data)).convert("RGB")


def background(svg: str) -> str:
    """The fill of a template's background rect, the first element after its <defs> line: what
    its ink map and focus are measured from. FIREPROOF_BG for a template laid out otherwise (a
    legacy piece's source.svg)."""
    m = _BACKGROUND.match(svg)
    return FIREPROOF_BG if m is None else m.group(1)


def _ink(img: Image.Image, bg: str) -> NDArray[np.float64]:
    pixels = np.asarray(img, dtype=np.float64)
    return np.linalg.norm(pixels - np.array(hex_to_rgb(bg), dtype=np.float64), axis=2)


def ink_map(img: Image.Image, bg: str, size: tuple[int, int] = (64, 36)) -> NDArray[np.float64]:
    """Per-pixel RGB distance from `bg` at `size`, flattened to a unit vector (all zeros when
    blank): what a design 'looks like'. The dot product of two maps is their cosine similarity."""
    d = _ink(img.resize(size), bg)
    n = float(np.linalg.norm(d))
    return d.ravel() / n if n > 0 else d.ravel()


def focus(img: Image.Image, bg: str) -> tuple[float, float]:
    """Ink-weighted centroid of `img` (weights = RGB distance from `bg`) as (x, y) fractions of
    its width and height, rounded to 4 dp; (0.5, 0.5) when nothing differs from `bg`."""
    d = _ink(img, bg)
    total = float(d.sum())
    if total == 0:
        return 0.5, 0.5
    h, w = int(d.shape[0]), int(d.shape[1])
    cols: NDArray[np.float64] = d.sum(axis=0)
    rows: NDArray[np.float64] = d.sum(axis=1)
    fx = float(np.dot(cols, np.arange(w, dtype=np.float64) + 0.5)) / total / w
    fy = float(np.dot(rows, np.arange(h, dtype=np.float64) + 0.5)) / total / h
    return round(fx, 4), round(fy, 4)

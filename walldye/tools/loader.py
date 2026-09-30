"""Importing a piece (design.py, or a legacy source.svg with its palette.yaml) and drawing
it to a Document, with the params a variant or --set gives it."""

import contextlib
import hashlib
import importlib.util
import itertools
import sys
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Final, cast, final

import yaml

from walldye._aspect import Aspect, canvas_size
from walldye._color import Color, mix, token
from walldye._design import Design, RenderSpec
from walldye._document import Document
from walldye._params import Params
from walldye._theme import normalize_seed
from walldye.tools import knobs, metadata, paths
from walldye.tools.errors import UsageError
from walldye.tools.themes import Theme, regime_of, tokens_of
from walldye.tools.tokenize import find_colors

sys.dont_write_bytecode = True  # imported designs must not leave __pycache__ in wallpapers/<slug>/


DESIGN_ERROR: Final = "design.py must define @design(...) def draw(s: Canvas[...]) -> None"


DOC_CACHE: Final = 16


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
        entries = metadata.as_dict(yaml.safe_load(palette_path.read_text()) or {})
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
    pair = metadata.as_list(value)
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
    d = paths.piece_dir(slug)
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
    path = paths.piece_dir(slug) / "design.py"
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

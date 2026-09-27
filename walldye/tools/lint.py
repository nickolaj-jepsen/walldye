"""Static lints of check steps 6-7: template limits, design.py source rules and meta.yaml rules."""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize as py_tokenize
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from walldye.tools import common

MAX_BYTES, WARN_BYTES = 1_000_000, 600_000
MAX_ELEMENTS, WARN_ELEMENTS = 20_000, 15_000
DESIGN_IMPORTS = ("walldye", "numpy", "scipy", "shapely", "skimage")
COLOUR_CALLS = ("luminance(", "hex_to_rgb(", "colorsys")
# Hues and named shades; copy must say "accent", "bg", roles. Token names (ALL CAPS) are fine.
COLOUR_WORDS = frozenset({
    "red", "orange", "yellow", "green", "blue", "purple", "violet", "pink", "brown", "black",
    "white", "grey", "gray", "cyan", "magenta", "teal", "turquoise", "indigo", "crimson",
    "scarlet", "maroon", "amber", "golden", "beige", "cream", "ivory", "terracotta", "ochre",
    "umber", "sepia", "navy", "lavender", "lilac", "mauve", "azure", "cobalt", "vermilion",
    "burgundy", "charcoal", "khaki", "sienna", "cerulean", "ultramarine", "chartreuse", "fuchsia"
})  # fmt: skip
RESERVED_SLUGS = frozenset({"about", "index", "t", "og", "fonts", "404", "robots", "favicon"})
SOURCE_KINDS = ("recreation", "inspiration", "reference", "data")
FAN_WORK = "LicenseRef-fan-work"
DEFAULT_LICENSE = "CC0-1.0"
LICENSES = common.ROOT / "LICENSES"


def reserved(slug: str) -> bool:
    """Whether `slug` collides with a site route or file (RESERVED_SLUGS, sitemap*, _*)."""
    return slug in RESERVED_SLUGS or slug.startswith(("sitemap", "_"))


def svg(text: str) -> tuple[list[str], list[str]]:
    """(errors, warnings) for one template: invalid XML, <text>, <filter>, <image>, size and
    element count over MAX_* are errors; over WARN_* warnings."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return [f"invalid XML: {e}"], []
    errors, warnings = [], []
    tags = [el.tag.rpartition("}")[2] for el in root.iter()]
    if "text" in tags:
        errors.append("<text> depends on installed fonts; draw glyphs as paths (walldye.glyphs)")
    if "filter" in tags:
        errors.append("<filter> is not allowed: slow at 4K, soft, and renderers disagree")
    if "image" in tags:
        errors.append("<image> is not allowed: templates are self-contained vectors")
    size = len(text.encode())
    for value, hard, soft, what in ((size, MAX_BYTES, WARN_BYTES, f"{size:,} bytes"), (len(tags), MAX_ELEMENTS, WARN_ELEMENTS, f"{len(tags)} elements")):
        if value > hard:
            errors.append(f"{what} is over the limit of {hard:,}; merge shapes into one <path> per colour")
        elif value > soft:
            warnings.append(f"{what} is heavy (over {soft:,}); merge shapes into one <path> per colour")
    return errors, warnings


def colour_words(text: str) -> set[str]:
    """Colour words in `text`, lowercased; ALL-CAPS words (token names like ORANGE_DARK) are not prose."""
    return {w.lower() for w in re.findall(r"\b[A-Za-z]+\b", text) if w.lower() in COLOUR_WORDS and not w.isupper()}


def source(path: Path) -> tuple[list[str], list[str]]:
    """(errors, warnings) for a design.py: imports outside the standard library and
    DESIGN_IMPORTS (including relative ones) are errors; COLOUR_CALLS and colour words in
    docstrings or comments are warnings. SyntaxError propagates."""
    text = path.read_text()
    tree = ast.parse(text, str(path))
    errors, warnings = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            errors.append(f"line {node.lineno}: relative import; designs are single files")
            continue
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
        for name in names:
            top = name.split(".")[0]
            if top not in sys.stdlib_module_names and top not in DESIGN_IMPORTS:
                errors.append(f"line {node.lineno}: imports {name}; designs may import the standard library and {', '.join(DESIGN_IMPORTS)}")
    for call in COLOUR_CALLS:
        if call in text:
            warnings.append(f"uses {call.rstrip('(')}: branch only on is_light() and colour only with tokens and mix()")
    docs = [ast.get_docstring(n) or "" for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    comments = [t.string for t in py_tokenize.generate_tokens(io.StringIO(text).readline) if t.type == py_tokenize.COMMENT]
    if words := colour_words("\n".join(docs + comments)):
        warnings.append(f"colour words in docstrings or comments: {', '.join(sorted(words))} (name tokens or roles, never hues)")
    return errors, warnings


def license_of(meta: dict) -> str | None:
    """The folder's licence: `license:`, else DEFAULT_LICENSE for an AI-generated piece with
    no recreation source, else None (no licence can be resolved)."""
    if meta.get("license"):
        return meta["license"]
    recreation = any(isinstance(s, dict) and s.get("kind") == "recreation" for s in meta.get("sources") or [])
    return DEFAULT_LICENSE if meta.get("ai_generated") is True and not recreation else None


def load_taxonomy() -> dict[str, set[str]] | None:
    """Allowed values per facet from taxonomy.yaml (each facet a list of values, or a mapping
    keyed by value); None when the file does not exist."""
    if not common.TAXONOMY.exists():
        return None
    data = yaml.safe_load(common.TAXONOMY.read_text()) or {}
    return {facet: set(values or ()) for facet, values in data.items()}


def meta(slug: str, m: dict, taxonomy: dict[str, set[str]] | None) -> tuple[list[str], list[str]]:
    """(errors, warnings) for the meta.yaml `m` of `slug`: required copy, reserved slugs,
    boolean draft and ai_generated, themes, source kinds, licence rules (including a
    LICENSES/<licence>.txt for the resolved licence), facets against `taxonomy` (skipped with a
    warning when None) and proposed_facets outside drafts; colour words in the copy warn."""
    errors, warnings = [], []
    for key in ("title", "description"):
        if not isinstance(m.get(key), str) or not m[key].strip():
            errors.append(f"meta.yaml needs a {key}")
    for key in ("draft", "ai_generated"):
        if key in m and not isinstance(m[key], bool):
            errors.append(f"{key} must be true or false, not {m[key]!r}")
    if reserved(slug):
        errors.append(f"slug {slug!r} is reserved by the site")
    themes = m.get("themes")
    if themes is not None and themes not in (["dark", "light"], ["dark"]):
        errors.append(f"themes must be [dark, light] or [dark], not {themes!r}")
    if themes == ["dark"] and not m.get("notes"):
        warnings.append("themes: [dark] needs the reason (light ladder steps 2-3 tried) in notes")
    sources = m.get("sources") or []
    if not isinstance(sources, list) or not all(isinstance(s, dict) for s in sources):
        errors.append("sources must be a list of mappings")
        sources = []
    for s in sources:
        if s.get("kind") not in SOURCE_KINDS:
            errors.append(f"source kind {s.get('kind')!r} is not one of {', '.join(SOURCE_KINDS)}")
    if not m.get("license"):
        if any(s.get("kind") == "recreation" for s in sources):
            errors.append("a kind: recreation source needs an explicit license: (ask the owner)")
        elif m.get("ai_generated") is not True:
            errors.append("human-made pieces need an explicit license:")
    if (licence := license_of(m)) and not (LICENSES / f"{licence}.txt").is_file():
        errors.append(f"license {licence!r} has no LICENSES/{licence}.txt; add the licence text or fix the id")
    franchise = m.get("franchise")
    if m.get("license") == FAN_WORK and not (isinstance(franchise, dict) and franchise.get("title") and franchise.get("owner")):
        errors.append(f"license {FAN_WORK} needs franchise: {{title, owner}}")
    if m.get("model") and m.get("ai_generated") is not True:
        errors.append("model: is only for ai_generated pieces")
    if taxonomy is None:
        warnings.append("taxonomy.yaml not found; facets not checked")
    else:
        for facet, allowed in taxonomy.items():
            values = m.get(facet) or []
            if not isinstance(values, list):
                errors.append(f"{facet} must be a list")
                continue
            for v in values:
                if v not in allowed:
                    errors.append(f"{facet}: {v!r} is not in taxonomy.yaml (suggest it under proposed_facets)")
    if m.get("proposed_facets") and not common.is_draft(m):
        errors.append("proposed_facets are only allowed while draft: true")
    return errors, warnings + copy_words(m)


def copy_words(m: dict) -> list[str]:
    """A warning naming the colour words in the title, description and notes of meta.yaml `m`, or []."""
    if words := colour_words("\n".join(str(m.get(k) or "") for k in ("title", "description", "notes"))):
        return [f"colour words in meta.yaml copy: {', '.join(sorted(words))} (describe the shape or what it picks out, without naming colours)"]
    return []


def pixel_origins(grids: list[tuple[float, float, float]]) -> list[str]:
    """Warnings for pixel helper grids (walldye.pixel_grids()) whose origin is not a whole unit."""
    off = sorted({(x, y, cell) for cell, x, y in grids if x % 1 or y % 1})
    return [f"pixel grid origin ({x:g}, {y:g}) is not a whole unit; snap it to the {cell:g}-unit cell grid" for x, y, cell in off]


"""A piece's folder and meta.yaml: the license, credit, sources, facets, variants and data/ rules."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import yaml

from walldye.tools import metadata, paths
from walldye.tools.lint.templates import Lints
from walldye.tools.lint.words import INTERNAL_TERMS, copy

RESERVED_SLUGS: Final = frozenset(
    {"about", "index", "t", "og", "fonts", "404", "robots", "favicon"}
)


FACETS: Final = ("technique", "subject", "lineage")
SOURCE_KINDS: Final = ("recreation", "inspiration", "reference", "data")


FAN_WORK: Final = "LicenseRef-fan-work"


DEFAULT_LICENSE: Final = "CC0-1.0"


# Kinds of source that say where the files in data/ come from.
DATA_KINDS: Final = ("data", "recreation")


LICENSES = paths.ROOT / "LICENSES"


DATA_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.(json|txt|npy)")


def reserved(slug: str) -> bool:
    """Whether `slug` collides with a site route or file (RESERVED_SLUGS, sitemap*, _*)."""
    return slug in RESERVED_SLUGS or slug.startswith(("sitemap", "_"))


def data(slug: str) -> list[str]:
    """Errors for wallpapers/<slug>/data/: only files named like `points.json`, `names.txt`
    or `grid.npy`, and no subdirectories."""
    d = paths.piece_dir(slug) / "data"
    if not d.is_dir():
        return []
    errors: list[str] = []
    for p in sorted(d.iterdir()):
        if p.is_dir():
            errors.append(f"data/{p.name}/: data/ holds files only, no subdirectories")
        elif DATA_NAME.fullmatch(p.name) is None:
            errors.append(f"data/{p.name}: data files are .json, .txt or .npy with a plain name")
    return errors


def _text(m: metadata.Meta, key: str) -> str:
    value = m.get(key)
    return value if isinstance(value, str) else ""


def _mappings(value: object) -> list[dict[str, object]] | None:
    """The mappings of a YAML list, [] for None, and None when it is not a list of mappings."""
    if value is None:
        return []
    items = metadata.as_list(value)
    if items is None:
        return None
    out = [e for e in map(metadata.as_dict, items) if e is not None]
    return out if len(out) == len(items) else None


def license_of(meta: metadata.Meta) -> str | None:
    """The folder's license: `license:`, else FAN_WORK when `franchise:` is set, else
    DEFAULT_LICENSE for a piece a model made (`model:`) with no recreation source, else None
    (no license can be resolved)."""
    if (license := _text(meta, "license")) != "":
        return license
    if "franchise" in meta:
        return FAN_WORK
    sources = _mappings(meta.get("sources"))
    recreation = sources is not None and any(s.get("kind") == "recreation" for s in sources)
    return DEFAULT_LICENSE if _text(meta, "model") != "" and not recreation else None


@dataclass(frozen=True)
class Taxonomy:
    """taxonomy.yaml: each facet's values with the words the site shows for them, and each
    model id's credit name."""

    facets: dict[str, dict[str, str]]
    models: dict[str, str]


def _labels(value: object, what: str) -> dict[str, str]:
    entries = dict[str, object]() if value is None else metadata.as_dict(value)
    if entries is None or not all(isinstance(v, str) and v.strip() != "" for v in entries.values()):
        raise ValueError(f"{paths.TAXONOMY.name}: {what} must map each value to its words")
    return {k: str(v) for k, v in entries.items()}


def load_taxonomy() -> Taxonomy | None:
    """taxonomy.yaml's FACETS and `models:`; None when the file does not exist. ValueError when
    one of them is not a mapping of values to non-empty words."""
    if not paths.TAXONOMY.exists():
        return None
    data = metadata.as_dict(yaml.safe_load(paths.TAXONOMY.read_text()))
    if data is None:
        raise ValueError(f"{paths.TAXONOMY.name}: must be a mapping")
    facets = {f: _labels(data.get(f), f) for f in FACETS}
    return Taxonomy(facets, _labels(data.get("models"), "models"))


def meta(
    slug: str,
    m: metadata.Meta,
    taxonomy: Taxonomy | None,
    variants: Sequence[str] = ("default",),
) -> Lints:
    """(errors, warnings) for the meta.yaml `m` of `slug`, whose design declares `variants`
    ("default" first). Facets and the model's credit name are skipped, with a warning, when
    `taxonomy` is None; color words in the copy warn."""
    errors: list[str] = []
    warnings: list[str] = []
    for key in ("title", "description"):
        if _text(m, key).strip() == "":
            errors.append(f"meta.yaml needs a {key}")
    if "draft" in m and not isinstance(m["draft"], bool):
        errors.append(f"draft must be true or false, not {m['draft']!r}")
    author, model = _text(m, "author").strip(), _text(m, "model").strip()
    if author == "" and model == "":
        errors.append("meta.yaml needs model: (the model id that made it) or author: (who did)")
    elif author != "" and model != "":
        errors.append("author: is for human-made pieces; a piece a model made has only model:")
    elif model != "" and taxonomy is not None and model not in taxonomy.models:
        errors.append(f"model {model!r} needs a credit name under models: in taxonomy.yaml")
    if reserved(slug):
        errors.append(f"slug {slug!r} is reserved by the site")
    sources = _mappings(m.get("sources"))
    if sources is None:
        errors.append("sources must be a list of mappings")
        sources = list[dict[str, object]]()
    for s in sources:
        if s.get("kind") not in SOURCE_KINDS:
            errors.append(f"source kind {s.get('kind')!r} is not one of {', '.join(SOURCE_KINDS)}")
        if "title" in s and "topic" in s:
            errors.append(
                f"source {s['title']!r}: a title names a work and a topic anything else; not both"
            )
        if all(_text(s, k).strip() == "" for k in ("title", "topic", "author")):
            errors.append("a source needs a title, a topic or an author")
    if (paths.WALLPAPERS / slug / "data").is_dir() and not any(
        s.get("kind") in DATA_KINDS for s in sources
    ):
        errors.append("data/ needs a kind: data source (or the recreation it comes from)")
    fan = "franchise" in m
    if _text(m, "license") != "":
        if fan:
            errors.append(f"franchise: makes the piece fan work ({FAN_WORK}); drop license:")
        elif m.get("license") == FAN_WORK:
            errors.append("fan work is marked by franchise: {title, owner}, not license:")
    elif not fan:
        if any(s.get("kind") == "recreation" for s in sources):
            errors.append("a kind: recreation source needs an explicit license: (ask the owner)")
        elif model == "":
            errors.append("human-made pieces need an explicit license:")
    if (license := license_of(m)) is not None and not (LICENSES / f"{license}.txt").is_file():
        errors.append(
            f"license {license!r} has no LICENSES/{license}.txt; add the license text or fix the id"
        )
    franchise = metadata.as_dict(m.get("franchise"))
    if fan and (franchise is None or "" in (_text(franchise, "title"), _text(franchise, "owner"))):
        errors.append("franchise needs a title and an owner")
    if taxonomy is None:
        warnings.append("taxonomy.yaml not found; facets not checked")
    else:
        for facet, allowed in taxonomy.facets.items():
            raw = m.get(facet)
            values = list[object]() if raw is None else metadata.as_list(raw)
            if values is None:
                errors.append(f"{facet} must be a list")
                continue
            for v in values:
                if v not in allowed:
                    errors.append(
                        f"{facet}: {v!r} is not in taxonomy.yaml (suggest it under proposed_facets)"
                    )
    if m.get("proposed_facets") not in (None, {}) and not metadata.is_draft(m):
        errors.append("proposed_facets are only allowed while draft: true")
    variant_errors, variant_warnings = _variants(m, variants)
    copy_warnings = [f"meta.yaml {w}" for w in copy(m)]
    return errors + variant_errors, warnings + copy_warnings + variant_warnings


def _variants(m: metadata.Meta, names: Sequence[str]) -> Lints:
    """The variants: rules: keys exactly the declared names, a unique plain label for each,
    and description and draft only on named variants."""
    if len(names) <= 1:
        if "variants" in m:
            return ["variants: is only for designs that declare named variants"], []
        return [], []
    entries = metadata.as_dict(m.get("variants"))
    if entries is None:
        return [f"meta.yaml needs variants: with a label for each of {', '.join(names)}"], []
    errors: list[str] = []
    warnings: list[str] = []
    if len(missing := [n for n in names if n not in entries]) > 0:
        errors.append(
            f"variants: missing {', '.join(missing)} (design.py declares {', '.join(names)})"
        )
    if len(extra := [n for n in entries if n not in names]) > 0:
        errors.append(
            f"variants: {', '.join(extra)} not declared in design.py (it declares {', '.join(names)})"
        )
    labels: dict[str, str] = {}
    for name, value in entries.items():
        entry = metadata.as_dict(value)
        if entry is None:
            errors.append(f"variants: {name} must be a mapping with a label")
            continue
        allowed = {"label"} if name == "default" else {"label", "description", "draft"}
        if len(unknown := sorted(set(entry) - allowed)) > 0:
            errors.append(
                f"variants: {name}: {', '.join(unknown)} not allowed (only {', '.join(sorted(allowed))})"
            )
        label = _text(entry, "label").strip()
        words = label.split()
        if not 1 <= len(words) <= 4:
            errors.append(f"variants: {name} needs a label of one to four plain words")
        stems = {w.lower().strip(".,;:!?").removesuffix("s") for w in words}
        if len(internal := sorted(stems & INTERNAL_TERMS)) > 0:
            errors.append(
                f"variants: {name}: the label says {', '.join(internal)}, a word visitors never see"
            )
        if (other := labels.get(label.lower())) is not None:
            errors.append(f"variants: {name} and {other} share the label {label!r}")
        labels[label.lower()] = name
        if "description" in entry and _text(entry, "description").strip() == "":
            errors.append(f"variants: {name}: description must be text")
        if "draft" in entry and not isinstance(entry["draft"], bool):
            errors.append(f"variants: {name}: draft must be true or false")
    return errors, warnings

"""`walldye list` (the pieces), `walldye params` (a design's params and variants) and
`walldye themes` (the presets), plus the vitest theme fixture."""

import dataclasses
import json
import re
import sys

from walldye import _theme
from walldye._params import KnobInfo, describe
from walldye.tools import check, common


def run_list() -> int:
    """Print one tab-separated line per piece: slug, title, description, `draft` or `-`, its
    native aspects and its named variants, each comma-joined (`error` and nothing when the
    design cannot be imported). A piece whose meta.yaml cannot be read is left out, with a
    note on stderr."""
    for slug in common.slugs():
        try:
            meta = common.load_meta(slug)
        except (OSError, ValueError) as e:
            print(f"list: left out {slug}: {e}", file=sys.stderr)
            continue
        try:
            piece = check.load(slug)
            aspects, variants = ",".join(piece.aspects), ",".join(piece.variants)
        except check.DesignError:
            aspects, variants = "error", ""
        one_line = [
            re.sub(r"\s+", " ", "" if (v := meta.get(k)) is None else str(v)).strip()
            for k in ("title", "description")
        ]
        draft = "draft" if common.is_draft(meta) else "-"
        print("\t".join([slug, *one_line, draft, aspects, variants]))
    return 0


def _value(v: object) -> str:
    if isinstance(v, bool) or v is None:
        return str(v).lower()
    if isinstance(v, float):
        return f"{v:g}"
    return repr(v) if isinstance(v, str) else str(v)


def _span(k: KnobInfo) -> str:
    if k.choices is not None:
        return "|".join(str(c) for c in k.choices)
    if k.lo is None and k.hi is None:
        return ""
    return f"{'' if k.lo is None else f'{k.lo:g}'}..{'' if k.hi is None else f'{k.hi:g}'}"


def _changes(piece: common.Piece) -> dict[str, dict[str, object]]:
    """{variant: {field: value}} with each named variant's fields that differ from the default."""
    default = piece.params()
    names = [k.name for k in describe(piece.params_type)]
    return {
        v: {n: getattr(p, n) for n in names if getattr(p, n) != getattr(default, n)}
        for v, p in piece.variants.items()
    }


def params(slug: str) -> dict[str, object]:
    """`walldye params --json` for `slug`: {slug, class, knobs: [KnobInfo as an object],
    variants: {name: {field: value}}} with only the fields that differ from the default."""
    piece = common.load(slug)
    return {
        "slug": slug,
        "class": piece.params_type.__name__,
        "knobs": [dataclasses.asdict(k) for k in describe(piece.params_type)],
        "variants": _changes(piece),
    }


def run_params(slug: str, as_json: bool) -> int:
    """Print the params schema of `slug`: the class name, one line per field (name, kind,
    default, lo..hi or the choices, unit, doc), then one line per named variant with the
    fields that differ from the default and its meta.yaml label, marked (draft) when so;
    with `as_json`, params() as JSON."""
    if as_json:
        print(json.dumps(params(slug), indent=2))
        return 0
    piece = common.load(slug)
    rows = [
        [k.name, k.kind, _value(k.default), _span(k), k.unit, k.doc]
        for k in describe(piece.params_type)
    ]
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    print(piece.params_type.__name__)
    for r in rows:
        print("  " + "  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip())
    labels = common.meta_variants(common.load_meta(slug))
    for name, fields in _changes(piece).items():
        values = " ".join(f"{k}={_value(v)}" for k, v in fields.items())
        entry = labels.get(name, {})
        label = entry.get("label")
        shown = f"  {label}" if isinstance(label, str) else ""
        draft = "  (draft)" if entry.get("draft") is True else ""
        print(f"{name}: {values}{shown}{draft}")
    return 0


def run_themes(seeds: dict[str, str] | None) -> int:
    """List the presets with their seeds and regime; with `seeds`, also print that theme's 21
    tokens."""
    for name in _theme.PRESETS:
        s = _theme.parse_seeds(name)
        regime = "light" if _theme.is_light(s["bg"], s["fg"]) else "dark"
        default = " (default)" if name == _theme.DEFAULT_THEME else ""
        print(f"{name:18} {s['bg']} {s['fg']} {s['accent']}  {regime}{default}")
    if seeds is not None:
        print(f"\n{_theme.theme_token(seeds)}:")
        for k, v in _theme.theme_tokens(seeds).items():
            print(f"  {k.upper():12} {v}")
    return 0

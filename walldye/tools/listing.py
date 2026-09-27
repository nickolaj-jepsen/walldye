"""`walldye list` (the pieces) and `walldye themes` (the presets and the vitest theme fixture)."""

from __future__ import annotations

import json
import re
import sys

import walldye
from walldye import _basis, _theme
from walldye.tools import common

FIXTURE = common.ROOT / "src/lib/__fixtures__/themes.json"
FIXTURE_SEED, FIXTURE_PER_REGIME = 1, 20
# Seed triples where regime selection is closest to a tie.
EDGE_CASES = [
    ("#808080", "#808080", "#CF6A4C"),
    ("#777777", "#787878", "#CF6A4C"),
    ("#787878", "#777777", "#CF6A4C"),
]


def run_list() -> int:
    """Print one tab-separated line per piece: slug, title, description, `draft` or `-`, and
    its native aspects comma-joined (`error` when design.py's ASPECTS cannot be read). A piece
    whose meta.yaml cannot be read is left out, with a note on stderr."""
    for slug in common.slugs():
        try:
            meta = common.load_meta(slug)
        except (OSError, ValueError) as e:
            print(f"list: left out {slug}: {e}", file=sys.stderr)
            continue
        try:
            aspects = ",".join(walldye.native_aspects(common.design_aspects(slug)))
        except (OSError, ValueError, SyntaxError):
            aspects = "error"
        one_line = [
            re.sub(r"\s+", " ", str(meta.get(k) or "")).strip() for k in ("title", "description")
        ]
        print("\t".join([slug, *one_line, "draft" if common.is_draft(meta) else "-", aspects]))
    return 0


def _entry(seeds: dict[str, str]) -> dict:
    return {
        "seeds": seeds,
        "light": _theme.is_light(seeds["bg"], seeds["fg"]),
        "tokens": walldye.theme_tokens(seeds),
    }


def fixture() -> dict:
    """The TS port's reference data: every preset, FIXTURE_PER_REGIME random seed triples per
    regime from _basis.generate(FIXTURE_SEED, ...), and EDGE_CASES, each as {seeds, light, tokens}
    with tokens in TOKENS order (fireproof's exact seeds resolve to its pinned table)."""
    random = _basis.generate(FIXTURE_SEED, FIXTURE_PER_REGIME)
    return {
        "presets": {name: _entry(walldye.parse_seeds(name)) for name in walldye.PRESETS},
        "random": {
            r: [_entry(dict(zip(walldye.SEEDS, t, strict=True))) for t in themes]
            for r, themes in random.items()
        },
        "edges": [_entry(dict(zip(walldye.SEEDS, t, strict=True))) for t in EDGE_CASES],
    }


def run_themes(seeds: dict[str, str] | None, write_json: bool) -> int:
    """List the presets with their seeds and regime; with `seeds`, also print that theme's 21
    tokens; with `write_json`, write fixture() to FIXTURE and print its path."""
    for name in walldye.PRESETS:
        s = walldye.parse_seeds(name)
        regime = "light" if _theme.is_light(s["bg"], s["fg"]) else "dark"
        default = " (default)" if name == walldye.DEFAULT_THEME else ""
        print(f"{name:18} {s['bg']} {s['fg']} {s['accent']}  {regime}{default}")
    if seeds:
        print(f"\n{walldye.theme_token(seeds)}:")
        for k, v in walldye.theme_tokens(seeds).items():
            print(f"  {k.upper():12} {v}")
    if write_json:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(fixture(), indent=2) + "\n")
        print(FIXTURE)
    return 0

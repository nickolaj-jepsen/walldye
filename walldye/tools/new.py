"""`walldye new`: scaffold wallpapers/<slug>/ with a starter design.py and a draft meta.yaml."""

from __future__ import annotations

import datetime
import sys

import yaml

from walldye.tools import common, lint

DESIGN = '''"""TODO: one theme-neutral line, concept + technique."""

from walldye import ACCENT, UI, H, W

# ASPECTS = ["any"]  # once the composition follows W and H; without it the piece is 16:9 only


def draw(s):
    u = min(W, H) / 1080  # short-side unit, so sizes survive any aspect
    cx, cy = W * 0.62, H * 0.5
    s.circle(cx, cy, 240 * u, fill="none", stroke=UI, stroke_width=2 * u)
    s.circle(cx, cy, 10 * u, fill=ACCENT)
'''


class _BlockDumper(yaml.SafeDumper):
    """Block style with indented sequences (`  - item`) and `|` blocks for multi-line text."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


class _MetaDumper(_BlockDumper):
    """_BlockDumper, but lists of scalars in flow style (`technique: [drafting]`)."""


_BlockDumper.add_representer(
    str, lambda d, v: d.represent_scalar("tag:yaml.org,2002:str", v, style="|" if "\n" in v else None)
)
_MetaDumper.add_representer(
    list,
    lambda d, v: d.represent_sequence(
        "tag:yaml.org,2002:seq", v, flow_style=not any(isinstance(x, (dict, list)) for x in v)
    ),
)


def dump_yaml(data: dict, flow_lists: bool = True) -> str:
    """`data` as YAML in the house style of meta.yaml (`flow_lists`) or taxonomy.yaml (block
    lists throughout), keys in insertion order. Comments do not survive a load and dump."""
    dumper = _MetaDumper if flow_lists else _BlockDumper
    return yaml.dump(data, Dumper=dumper, sort_keys=False, allow_unicode=True, width=1000)


def write_meta(slug: str, meta: dict) -> None:
    (common.piece_dir(slug) / "meta.yaml").write_text(dump_yaml(meta))


def run(slug: str, author: str, model: str) -> int:
    """Create wallpapers/<slug>/ holding DESIGN and a meta.yaml with ai_generated true, added
    today, draft true and no license line. Exits with a message if `slug` is malformed,
    reserved or already taken."""
    try:
        d = common.piece_dir(slug)
    except ValueError as e:
        sys.exit(str(e))
    if lint.reserved(slug):
        sys.exit(f"{slug!r} is reserved for a site route")
    if d.exists():
        sys.exit(f"{d} already exists")
    d.mkdir(parents=True)
    (d / "design.py").write_text(DESIGN)
    write_meta(slug, {
        "title": slug.replace("-", " ").capitalize(),
        "description": "",
        "technique": [],
        "subject": [],
        "lineage": [],
        "sources": [],
        "added": datetime.date.today(),
        "author": author,
        "ai_generated": True,
        "model": model,
        "draft": True,
        "proposed_facets": {},
    })  # fmt: skip
    print(d)
    return 0

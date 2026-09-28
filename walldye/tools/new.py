"""`walldye new`: scaffold wallpapers/<slug>/ with a starter design.py and a draft meta.yaml."""

import datetime
import sys
from collections.abc import Mapping
from typing import override

import yaml

from walldye.tools import common, lint

DESIGN = '''"""TODO: one theme-neutral line, concept + technique."""

from walldye import ACCENT, UI, Canvas, P, design


@design()  # aspects="any" once the composition follows s.w and s.h
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.4))
    s.stroke(P().circle(c, 240), UI, 2)
    s.fill(P().circle(c, 10), ACCENT)
'''


class _BlockDumper(yaml.SafeDumper):
    """Block style with indented sequences (`  - item`) and `|` blocks for multi-line text."""

    @override
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


class _MetaDumper(_BlockDumper):
    """_BlockDumper, but lists of scalars in flow style (`technique: [drafting]`)."""


def _str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


def _flow_list(dumper: yaml.SafeDumper, value: list[object]) -> yaml.SequenceNode:
    flow = not any(isinstance(x, (dict, list)) for x in value)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", value, flow_style=flow)


_BlockDumper.add_representer(str, _str)
_MetaDumper.add_representer(list, _flow_list)


def dump_yaml(data: Mapping[str, object], flow_lists: bool = True) -> str:
    """`data` as YAML in the house style of meta.yaml (`flow_lists`) or taxonomy.yaml (block
    lists throughout), keys in insertion order. Comments do not survive a load and dump."""
    dumper = _MetaDumper if flow_lists else _BlockDumper
    return yaml.dump(dict(data), Dumper=dumper, sort_keys=False, allow_unicode=True, width=1000)


def write_meta(slug: str, meta: Mapping[str, object]) -> None:
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
        "added": datetime.datetime.now().astimezone().date(),
        "author": author,
        "ai_generated": True,
        "model": model,
        "draft": True,
        "proposed_facets": {},
    })  # fmt: skip
    print(d)
    return 0

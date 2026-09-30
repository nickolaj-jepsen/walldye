"""meta.yaml, and the loose readers for parsed YAML and JSON that type-check each value."""

from collections.abc import Mapping
from typing import cast, override

import yaml

from walldye.tools import paths

type Meta = dict[str, object]


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
    path = paths.piece_dir(slug) / "meta.yaml"
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
    (lint.piece.meta reports them)."""
    out: dict[str, dict[str, object]] = {}
    variants = as_dict(meta.get("variants"))
    if variants is None:
        return out
    for name, entry in variants.items():
        if (e := as_dict(entry)) is not None:
            out[name] = e
    return out


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
    (paths.piece_dir(slug) / "meta.yaml").write_text(dump_yaml(meta))

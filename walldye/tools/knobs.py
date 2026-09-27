"""Params from the command line: `--set k=v`, `--wedge k=SPEC` and `--seeds A..B`."""

import dataclasses
import math
from collections.abc import Sequence

from walldye._params import KnobInfo, Params, describe

type Value = int | float | bool | str | None

MAX_CELLS = 64
_BOOLS = {"true": True, "1": True, "false": False, "0": False}


def knob(params_type: type[Params], name: str) -> KnobInfo:
    """The schema entry of field `name`; ValueError naming the fields when there is none."""
    infos = describe(params_type)
    for info in infos:
        if info.name == name:
            return info
    names = ", ".join(i.name for i in infos)
    raise ValueError(f"{params_type.__name__} has no param {name!r} (has: {names})")


def parse(info: KnobInfo, text: str) -> Value:
    """`text` as a value of the field's kind: int by int(), float by float(), bool from
    true/false/1/0, str as given, seed as an int or `none`. ValueError otherwise."""
    try:
        if info.kind == "int":
            return int(text)
        if info.kind == "float":
            return float(text)
        if info.kind == "seed":
            return None if text.lower() == "none" else int(text)
    except ValueError:
        raise ValueError(f"{info.name} takes {info.kind} values, got {text!r}") from None
    if info.kind == "bool":
        if text.lower() not in _BOOLS:
            raise ValueError(f"{info.name} takes true, false, 1 or 0, got {text!r}")
        return _BOOLS[text.lower()]
    return text


def outside(info: KnobInfo, value: Value) -> str | None:
    """`name=value is outside lo..hi` when a number lies outside the field's soft range."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    lo, hi = info.lo, info.hi
    if (lo is None or value >= lo) and (hi is None or value <= hi):
        return None
    span = f"{'' if lo is None else f'{lo:g}'}..{'' if hi is None else f'{hi:g}'}"
    return f"{info.name}={value:g} is outside {span}"


def replace[Pm: Params](params: Pm, changes: dict[str, Value]) -> Pm:
    """`params` with `changes` applied; TypeError and ValueError from the params class propagate."""
    return dataclasses.replace(params, **changes)


def override[Pm: Params](params: Pm, items: Sequence[str]) -> tuple[Pm, list[str]]:
    """`params` with each `k=v` of `items` applied, and a warning per value outside its soft
    range. ValueError for a malformed item, an unknown field or an unparsable value; the
    params class raises TypeError or ValueError for a value it refuses."""
    changes: dict[str, Value] = {}
    warnings: list[str] = []
    for item in items:
        name, sep, text = item.partition("=")
        if sep == "":
            raise ValueError(f"--set takes k=v, got {item!r}")
        info = knob(type(params), name)
        changes[name] = parse(info, text)
        if (w := outside(info, changes[name])) is not None:
            warnings.append(w)
    return replace(params, changes), warnings


def wedge(info: KnobInfo, spec: str) -> list[Value]:
    """The values of `--wedge k=SPEC`: `a..b..step` counts from a to b, including b when it
    lands on a step within 1e-9 (ints when a, b and step are all ints), and `v1,v2,...` lists
    values parsed by the field's kind. ValueError for anything else or an empty range."""
    parts = spec.split("..")
    if len(parts) == 1:
        return [parse(info, v) for v in spec.split(",")]
    if len(parts) != 3:
        raise ValueError(f"--wedge {info.name}={spec}: want a..b..step or v1,v2,...")
    if all(_is_int(p) for p in parts):
        a, b, step = (int(p) for p in parts)
        return [a + k * step for k in range(_count(a, b, step, info.name, spec))]
    try:
        x, y, dx = (float(p) for p in parts)
    except ValueError:
        raise ValueError(f"--wedge {info.name}={spec}: a, b and step are numbers") from None
    return [x + k * dx for k in range(_count(x, y, dx, info.name, spec))]


def _count(a: float, b: float, step: float, name: str, spec: str) -> int:
    if step <= 0 or b < a or not all(math.isfinite(v) for v in (a, b, step)):
        raise ValueError(f"--wedge {name}={spec}: want a <= b and a step above 0")
    return math.floor((b - a) / step + 1e-9) + 1


def _is_int(text: str) -> bool:
    try:
        int(text)
    except ValueError:
        return False
    return True


def seeds(spec: str) -> list[int]:
    """The seeds of `--seeds A..B`, A to B inclusive; ValueError unless 0 <= A <= B are ints."""
    a, sep, b = spec.partition("..")
    if sep == "" or not (_is_int(a) and _is_int(b)) or not 0 <= int(a) <= int(b):
        raise ValueError(f"--seeds takes A..B with whole numbers 0 <= A <= B, got {spec!r}")
    return list(range(int(a), int(b) + 1))

import dataclasses
import json
import re
import subprocess
import types
from pathlib import Path
from typing import Literal

import numpy as np
import pytest

from walldye import Params, knob
from walldye._params import KnobInfo, describe
from walldye.tools import common

TYPING = Path(__file__).parent / "typing"


class Moon(Params):
    size: Literal["s", "m", "l"] = knob(default="m", choices=("s", "m"))
    phase: float = knob(default=58, lo=-150, hi=150, unit="deg", doc="sun angle from the viewer")
    method: Literal["bayer", "bluenoise"] = knob(default="bluenoise", doc="dither method")
    cells: int = knob(default=3, choices=(2, 3, 4))
    label: str = knob(default="a", choices=("a", "b"), doc="which label")
    earthshine: bool = True
    steps: int = 12


def test_defaults_and_conversion():
    m = Moon()
    assert (m.phase, m.method, m.cells, m.earthshine, m.seed) == (58.0, "bluenoise", 3, True, None)
    assert type(m.phase) is float
    assert Moon(phase=90) == Moon(phase=90.0)
    assert hash(Moon(phase=90)) == hash(Moon(phase=90.0))
    assert type(Moon(cells=np.int64(4)).cells) is int
    assert Moon(phase=np.float32(2.5)).phase == 2.5
    assert Moon(seed=np.int64(3)).seed == 3
    assert Moon(phase=400).phase == 400.0  # soft range: variants may go outside it
    assert {Moon(): 1}[Moon()] == 1


def test_frozen_and_keyword_only():
    m = Moon()
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.phase = 3.0
    with pytest.raises(TypeError):
        Moon(1.0)
    assert dataclasses.replace(m, seed=3).seed == 3
    with pytest.raises(ValueError):
        dataclasses.replace(m, cells=5)


@pytest.mark.parametrize(
    ("kw", "error"),
    [
        ({"phase": "x"}, TypeError),
        ({"phase": True}, TypeError),
        ({"phase": float("nan")}, ValueError),
        ({"phase": 1 + 2j}, TypeError),
        ({"method": "nope"}, ValueError),
        ({"method": 1}, TypeError),
        ({"cells": 5}, ValueError),
        ({"cells": True}, TypeError),
        ({"cells": 3.0}, TypeError),
        ({"label": "c"}, ValueError),
        ({"earthshine": 1}, TypeError),
        ({"earthshine": np.True_}, TypeError),
        ({"seed": -1}, ValueError),
        ({"seed": True}, TypeError),
        ({"seed": 1.0}, TypeError),
        ({"steps": "3"}, TypeError),
        ({"size": "l"}, ValueError),
        ({"size": "xl"}, ValueError),
    ],
)
def test_instance_validation(kw, error):
    with pytest.raises(error):
        Moon(**kw)


NO_DEFAULT = object()


@pytest.mark.parametrize(
    ("name", "annotation", "default", "error", "match"),
    [
        ("x", int, NO_DEFAULT, TypeError, "no default"),
        ("x", int, dataclasses.field(), TypeError, "no default"),
        ("_x", int, 1, TypeError, "'_'"),
        ("seed", int, 1, TypeError, "seed"),
        ("x", list, [], TypeError, "a param is"),
        ("x", int | None, None, TypeError, "a param is"),
        ("x", Literal["a", 1], "a", TypeError, "a param is"),
        ("x", Literal[True], True, TypeError, "a param is"),
        ("x", str, knob(default="a", lo=1), TypeError, "lo and hi"),
        ("x", bool, knob(default=True, lo=0), TypeError, "lo and hi"),
        ("x", int, knob(default=1, choices=(1, 2), lo=0), TypeError, "not both"),
        ("x", float, knob(default=1.0, choices=(1.0,)), TypeError, "choices"),
        ("x", int, knob(default=1, lo=3, hi=2), ValueError, "above"),
        ("x", int, knob(default=5, lo=6, hi=10), ValueError, "outside"),
        ("x", int, knob(default=5, choices=(1, 2)), ValueError, "one of"),
        ("x", int, knob(default=1, choices=()), ValueError, "empty"),
        ("x", int, "a", TypeError, "takes an int"),
    ],
)
def test_class_creation_errors(name, annotation, default, error, match):
    ns: dict[str, object] = {"__annotations__": {name: annotation}}
    if default is not NO_DEFAULT:
        ns[name] = default
    with pytest.raises(error, match=match):
        types.new_class("X", (Params,), {}, lambda body: body.update(ns))


def test_describe():
    info = describe(Moon)
    assert [k.name for k in info] == [
        "size",
        "phase",
        "method",
        "cells",
        "label",
        "earthshine",
        "steps",
        "seed",
    ]
    assert info[0].choices == ("s", "m")
    assert info[1] == KnobInfo(
        "phase", "float", 58.0, -150.0, 150.0, None, "sun angle from the viewer", "deg"
    )
    assert info[2] == KnobInfo(
        "method", "str", "bluenoise", None, None, ("bayer", "bluenoise"), "dither method", ""
    )
    assert info[3].choices == (2, 3, 4) and info[3].kind == "int"
    assert info[5] == KnobInfo("earthshine", "bool", True, None, None, None, "", "")
    assert info[-1].kind == "seed" and info[-1].default is None
    assert [k.name for k in describe(Params)] == ["seed"]

    class Sub(Moon):
        extra: int = knob(default=2, lo=0, hi=9)

    assert [k.name for k in describe(Sub)][-2:] == ["extra", "seed"]
    assert Sub(extra=3, phase=1).phase == 1.0
    with pytest.raises(TypeError):
        describe(int)


def pyrefly_errors(*files: Path) -> set[tuple[str, int, str]]:
    """Pyrefly's findings in `files` at the level walldye check types designs at."""
    exe = common.tool("pyrefly")
    assert exe is not None
    cmd = [str(exe), "check", "-c", str(common.DESIGN_PYREFLY), "--output-format", "json"]
    out = subprocess.run([*cmd, *map(str, files)], capture_output=True, text=True, check=False)
    return {(Path(e["path"]).name, e["line"], e["name"]) for e in json.loads(out.stdout)["errors"]}


def test_types_catch_the_planted_mistakes():
    bad = TYPING / "bad.py"
    want = {
        ("bad.py", n, m.group(1))
        for n, line in enumerate(bad.read_text().splitlines(), 1)
        if (m := re.search(r"# expect: ([\w-]+)$", line))
    }
    assert len(want) >= 15
    assert pyrefly_errors(TYPING / "good.py", bad) == want

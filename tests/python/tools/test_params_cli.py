import json
from typing import Literal

import pytest
from PIL import Image
from tools_support import versions

from walldye import Params, knob
from walldye._params import describe
from walldye.tools import cli, knobs


class Moon(Params):
    phase: float = knob(default=58, lo=-150, hi=150, unit="deg", doc="sun angle")
    method: Literal["bayer", "bluenoise"] = knob(default="bluenoise", doc="dither method")
    cells: int = knob(default=3, choices=(2, 3, 4))
    count: int = knob(default=5, lo=1)
    earthshine: bool = True
    name: str = "moon"


def info(name: str):
    return knobs.knob(Moon, name)


@pytest.mark.parametrize(
    ("field", "text", "value"),
    [
        ("phase", "90", 90.0),
        ("phase", "-1.5", -1.5),
        ("cells", "4", 4),
        ("earthshine", "false", False),
        ("earthshine", "1", True),
        ("earthshine", "TRUE", True),
        ("name", "sun=x", "sun=x"),
        ("seed", "none", None),
        ("seed", "11", 11),
    ],
)
def test_parse(field, text, value):
    parsed = knobs.parse(info(field), text)
    assert parsed == value and type(parsed) is type(value)


@pytest.mark.parametrize(
    ("field", "text"), [("phase", "x"), ("cells", "2.5"), ("earthshine", "yes"), ("seed", "-")]
)
def test_parse_rejects(field, text):
    with pytest.raises(ValueError, match=field):
        knobs.parse(info(field), text)


def test_override():
    p, warnings = knobs.override(Moon(), ["phase=400", "method=bayer", "count=0", "seed=3"])
    assert p == Moon(phase=400, method="bayer", count=0, seed=3)
    assert warnings == ["phase=400 is outside -150..150", "count=0 is outside 1.."]
    assert knobs.override(Moon(), []) == (Moon(), [])
    with pytest.raises(
        ValueError,
        match=r"Moon has no param 'size' \(has: phase, method, cells, count, earthshine, name, seed\)",
    ):
        knobs.override(Moon(), ["size=3"])
    with pytest.raises(ValueError, match="--set takes k=v"):
        knobs.override(Moon(), ["phase"])
    with pytest.raises(ValueError, match="takes one of"):
        knobs.override(Moon(), ["method=riemersma"])
    with pytest.raises(ValueError, match="takes one of"):
        knobs.override(Moon(), ["cells=5"])
    with pytest.raises(ValueError):
        knobs.override(Moon(), ["seed=-2"])


@pytest.mark.parametrize(
    ("field", "spec", "values"),
    [
        ("phase", "0..90..30", [0, 30, 60, 90]),
        ("phase", "0..100..30", [0, 30, 60, 90]),
        ("phase", "0..1..0.1", [k * 0.1 for k in range(11)]),
        ("phase", "0.5..1.5..0.5", [0.5, 1.0, 1.5]),
        ("method", "bayer,bluenoise", ["bayer", "bluenoise"]),
        ("cells", "2,4", [2, 4]),
        ("earthshine", "true,false", [True, False]),
        ("phase", "7", [7.0]),
    ],
)
def test_wedge(field, spec, values):
    got = knobs.wedge(info(field), spec)
    assert got == pytest.approx(values) if field == "phase" else got == values
    if spec == "0..90..30":
        assert all(type(v) is int for v in got)


@pytest.mark.parametrize(
    "spec", ["1..2", "0..1..0", "2..1..1", "0..x..1", "0..1..-1", "1..2..3..4"]
)
def test_wedge_rejects(spec):
    with pytest.raises(ValueError, match="--wedge phase="):
        knobs.wedge(info("phase"), spec)


def test_seeds():
    assert knobs.seeds("0..3") == [0, 1, 2, 3]
    assert knobs.seeds("5..5") == [5]
    for bad in ("3..1", "0-3", "a..b", "-1..2"):
        with pytest.raises(ValueError, match="--seeds"):
            knobs.seeds(bad)


def test_outside_soft_range():
    assert knobs.outside(info("phase"), 151) == "phase=151 is outside -150..150"
    assert knobs.outside(info("phase"), 150) is None
    assert (
        knobs.outside(info("name"), "x") is None and knobs.outside(info("earthshine"), True) is None
    )
    assert describe(Moon)[-1].name == "seed"


def test_params_command(wallpapers, capsys):
    versions(wallpapers)
    assert cli.main(["params", "versions"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Clock",
        "  hour  float  2     0..12  h  where the disc sits",
        "  ring  bool   true            the ring behind the disc",
        "  seed  seed   none            moves every random stream",
        "late: hour=8  Eight o'clock  (draft)",
        "bare: hour=5 ring=false seed=3  Five, no ring  (draft)",
    ]
    assert cli.main(["params", "versions", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["slug"] == "versions" and data["class"] == "Clock"
    assert data["knobs"][0] == {
        "name": "hour", "kind": "float", "default": 2.0, "lo": 0.0, "hi": 12.0,
        "choices": None, "doc": "where the disc sits", "unit": "h",
    }  # fmt: skip
    assert data["variants"] == {
        "late": {"hour": 8.0},
        "bare": {"hour": 5.0, "ring": False, "seed": 3},
    }


def test_set_on_render_and_preview(wallpapers, tmp_path, monkeypatch, capsys):
    versions(wallpapers)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["render", "versions", "--set", "hour=13", "-o", "a.svg"]) == 0
    assert "warning: hour=13 is outside 0..12" in capsys.readouterr().err
    assert cli.main(["render", "versions", "--variant", "late", "-o", "b.svg"]) == 0
    assert cli.main(["render", "versions", "--set", "hour=8", "-o", "c.svg"]) == 0
    assert (tmp_path / "b.svg").read_text() == (tmp_path / "c.svg").read_text()
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path / "prev"))
    args = ["preview", "versions", "--variant", "late", "--set", "ring=false", "--set", "hour=9.5"]
    assert cli.main([*args, "--width", "64"]) == 0
    png = capsys.readouterr().out.splitlines()[-1]
    assert png.endswith("versions--late-fireproof-16x9-set-hour-9.5-set-ring-false.png")
    for bad in (
        ["render", "versions", "--set", "size=3"],
        ["render", "versions", "--set", "ring=maybe"],
        ["preview", "versions", "--set", "hour"],
        ["build", "versions", "--set", "hour=3"],
        ["render", "versions", "--variant", "early"],
    ):
        with pytest.raises(SystemExit) as e:
            cli.main(bad)
        assert e.value.code == 2
    err = capsys.readouterr().err
    assert "--set is for exploring; give the values a named variant in design.py" in err
    assert "versions has no variant 'early' (have: default, late, bare)" in err


def test_wedge_sheet(wallpapers, tmp_path, capsys):
    versions(wallpapers)
    out = tmp_path / "s.png"
    args = [
        "sheet",
        "versions",
        "--wedge",
        "hour=0..9..3",
        "--seeds",
        "1..2",
        "--thumb",
        "64",
        "-o",
        str(out),
    ]
    assert cli.main(args) == 0
    assert capsys.readouterr().out.strip() == str(out)
    # 4 hours by 2 seeds, one row per hour
    assert Image.open(out).size == (8 + 2 * (64 + 8), 4 * (36 + 8 + 22) + 8)
    many = ["sheet", "versions", "--wedge", "hour=0..12..1", "--seeds", "0..4"]
    for bad in (
        many,
        ["sheet", "versions", "--wedge", "hour=a..b..c"],
        ["sheet", "versions", "--wedge", "ring=true", "--wedge", "ring=false"],
        ["sheet", "versions", "--wedge", "size=1,2"],
        ["sheet", "versions", "versions", "--seeds", "0..1"],
    ):
        with pytest.raises(SystemExit) as e:
            cli.main(bad)
        assert e.value.code == 2
    assert "65 cells is over the limit of 64" in capsys.readouterr().err


def test_wedge_sheet_warns_outside_soft_ranges(wallpapers, tmp_path, capsys):
    versions(wallpapers)
    args = ["sheet", "versions", "--variant", "bare", "--wedge", "hour=11,13", "--thumb", "32"]
    assert cli.main([*args, "-o", str(tmp_path / "w.png")]) == 0
    assert capsys.readouterr().err == "warning: hour=13 is outside 0..12\n"

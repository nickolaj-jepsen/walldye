"""scripts/port/codemod.py on six v1 fixture designs, and scripts/port/smoke.py on its output.

The codemod runs in its own uv script environment (it needs libcst), so it is driven as a
subprocess; tests skip when uv is not on PATH.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CODEMOD = ROOT / "scripts" / "port" / "codemod.py"
SMOKE = ROOT / "scripts" / "port" / "smoke.py"
FIXTURES = Path(__file__).parent / "fixtures"
NAMES = ("basic", "colours", "groups", "pixels", "seeded", "v1_walldye")


def codemod(*args: str | Path) -> subprocess.CompletedProcess[str]:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    cmd = [uv, "run", "--quiet", str(CODEMOD), *map(str, args)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=ROOT)


@pytest.fixture(scope="module")
def converted(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("port")
    done = codemod(FIXTURES, "--out", out / "out", "--report", out / "report.json")
    assert done.returncode == 0, done.stderr
    again = codemod(out / "out", "--out", out / "again", "--report", out / "again.json")
    assert again.returncode == 0, again.stderr
    return out


def source(converted: Path, name: str) -> str:
    return (converted / "out" / name / "design.py").read_text()


def report(converted: Path, name: str = "report.json") -> dict[str, dict[str, object]]:
    data = json.loads((converted / name).read_text())
    return {f["slug"]: f for f in data["files"]}


def todo_kinds(converted: Path, name: str) -> set[str]:
    todos = report(converted)[name]["todos"]
    assert isinstance(todos, list)
    return {t["kind"] for t in todos}


def test_every_fixture_converts_and_compiles(converted: Path) -> None:
    files = report(converted)
    assert set(files) == set(NAMES)
    for name, entry in files.items():
        assert entry["compiles"], name
        assert "error" not in entry, name
        compile(source(converted, name), name, "exec")


def test_a_second_run_changes_nothing(converted: Path) -> None:
    for name in NAMES:
        again = (converted / "again" / name / "design.py").read_text()
        assert again == source(converted, name), name
    assert all(not f["changes"] for f in report(converted, "again.json").values())


def test_output_is_ruff_formatted(converted: Path) -> None:
    fmt = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "--config", ROOT / "pyproject.toml"]
        + [converted / "out" / n / "design.py" for n in NAMES],
        capture_output=True,
        text=True,
        check=False,
    )
    assert fmt.returncode == 0, fmt.stdout + fmt.stderr


def test_elements_paths_and_the_path_builder(converted: Path) -> None:
    text = source(converted, "basic")
    for snippet in (
        "@design()\ndef draw(s: Canvas) -> None:",
        "s.fill(P().rect(0, 0, s.w, s.h), BG_ALT)",
        "s.stroke(P().circle((CX, CY), R), UI, 2)",
        "s.fill(P().circle(spoke(30), 6), ACCENT)",
        "s.stroke(P().rrect(40, 40, 200, 120, 12), UI_HI, 1.5)",
        "s.stroke(P().M(0, s.h - 40).L(s.w, s.h - 40), UI, 1, dash=DASH)",
        "DASH = (8, 6)",
        "s.stroke(P().poly([(10, 10), (60, 30), (110, 10)]), UI_HI, 1.2)",
        "closed=True),\n        mix(UI, ACCENT, 0.5),",
        "s.stroke(rays, UI, 1, dash=(4, 4))",
        "s.stroke(rays, UI_HI, 1)",  # v1's implicit black fill is dropped
        "P().M(spoke(0)).A(R, R, 0, True, 1, spoke(90))",
        's.stroke(arc, ACCENT, 3, cap="round")',
        "P().spline([",
        "s.stroke(wave, tone, 1 + i / 2)",
        "P().poly(list(zip([500, 560, 620], [900, 950, 900])))",
        "polar((CX, CY), R, deg=a)",
        "TONES = ladder((BG, ACCENT_4, ACCENT), 5)",
        "W, H = 1920, 1080",
    ):
        assert snippet in text, snippet
    assert "wallgen" not in text
    assert "import math" not in text  # its only use became deg=
    assert todo_kinds(converted, "basic") == {"aspects", "module-wh", "reads-wh", "star-args"}
    lines = text.splitlines()
    marked = lines[lines.index("    s.stroke(P().circle((CX, CY), min(*spoke(45), R)), UI, 1)") - 1]
    assert marked.strip().startswith("# TODO(port): star-args:")


def test_generators_come_from_the_canvas(converted: Path) -> None:
    text = source(converted, "seeded")
    for snippet in (
        "r = s.rng(3)",
        "n = s.noise(5)",
        "g = s.np_rng(7)",
        "noise_grid(40, 20, 8, s.np_rng(4), octaves=2)",
        "def ng(s: Canvas, cols, rows, scale, **kw):",
        'noise_grid(c, r, scale, s.np_rng(kw.pop("seed", 0)), **kw)',
        "pad = ng(s, 30, 30, 8, seed=9, octaves=3)",
        "def terrain(s: Canvas, seed):",
        "range(0, s.w, 40)",
        "terrain(s, 11)",
        "def picks(canvas: Canvas, seed):",  # it has its own s
        "canvas.rng(seed).shuffle(s)",
        "picks(s, 2)",
        "poisson_disk(Rect(50, 50, s.w - 100, s.h - 100), 60, r)",
    ):
        assert snippet in text, snippet
    assert "import numpy" not in text
    assert todo_kinds(converted, "seeded") == {"aspects", "generator", "unseeded"}


def test_group_fill_moves_onto_children(converted: Path) -> None:
    text = source(converted, "groups")
    for snippet in (
        "with s.group(stroke=UI, stroke_width=2):",
        's.path(P().circle((400, 400), 100), fill="none")',
        's.path(P().M(0, 0).L(100, 100), fill="none", stroke=ACCENT)',
        "Affine.translate(s.w / 2, s.h / 2) @ Affine.rotate(deg=15)",
        "s.fill(P().rect(-50, -50, 100, 100), UI_ALT)",
        "s.fill(P().rect(60, -50, 40, 40), ACCENT)",
        "s.linear_gradient([(0, BG), (1, ACCENT, 0.5)], (0, 0), (s.w, 0))",
        's.radial_gradient([(0, ACCENT), (1, BG)], (0.5, 0.5), 0.5, units="bbox")',
        "s.fill(P().rect(0, 0, s.w, s.h), UI_ALT, opacity=0.5)",
        "if not edge.empty:",
        "from walldye.geom import Affine",
    ):
        assert snippet in text, snippet
    assert "fill=UI_ALT, transform" not in text
    assert todo_kinds(converted, "groups") == {
        "aspects",
        "fill-default",
        "group-fill",
        "raw-markup",
    }


def test_pixel_helpers_take_v2_arguments(converted: Path) -> None:
    text = source(converted, "pixels")
    for snippet in (
        'dither(tone[:ROWS, :COLS] * 0.9, 3, method="bayer", matrix=4)',
        "grid_runs(s, grid, [BG, UI, ACCENT], CELL, (12, 30))",
        "[[m[j % 4][i % 4] for i in range(8)] for j in range(8)], dtype=float",
        'method="bluenoise",\n        rng=s.np_rng(3),',
        "grid_runs(s, speck, [None, UI_HI], 4, (1500, 40), skip=0)",
        'glyphs(s, ["LEVEL " + SHADES], UI_HI, at=(100, 900), font="5x8", px=2)',
        "at=(0, 940)",
        'sprite(s, ART, {"#": GREYS[5]}, 4, (1700, 900))',
        'SHADES = " ░▒▓█"',
        "GREYS = [BLACK, BG_DEEP, BG, BG_ALT, UI, UI_ALT, UI_HI, MUTED]",
        "from walldye.pixel import bayer, dither, glyphs, grid_runs, sprite",
    ):
        assert snippet in text, snippet
    assert todo_kinds(converted, "pixels") == {"aspects"}


def test_what_the_codemod_cannot_do_is_marked(converted: Path) -> None:
    text = source(converted, "colours")
    assert "@design(bg=BG_DEEP)" in text
    assert "\nBG = " not in text
    assert todo_kinds(converted, "colours") == {
        "aspects",
        "colour-order",
        "hex-literal",
        "lint",
        "removed-name",
        "string-path",
    }
    lines = text.splitlines()
    marked = lines[lines.index("    for (w, tone), d in sorted(buckets.items()):") - 1]
    assert marked.strip().startswith("# TODO(port): colour-order:")


def test_v1_walldye_aspects_unit_and_regime(converted: Path) -> None:
    text = source(converted, "v1_walldye")
    for snippet in (
        '@design(aspects="any")',
        "R = 300\n",
        "(s.w * 0.7, s.h / 2) if s.w > s.h else (s.w / 2, s.h * 0.6)",
        "edge = by_regime(BG_ALT, UI)",
        "s.stroke(P().circle((cx, cy), R), edge, 2)",
        "if s.light:",
        "s.stroke(P().M(0, 0).L(s.w, s.h), UI, 1)",
    ):
        assert snippet in text, snippet
    body = text.split("\n", 1)[1]  # past the docstring
    for gone in ("ASPECTS", "U =", "is_light", "W, H"):
        assert gone not in body, gone
    assert todo_kinds(converted, "v1_walldye") == set()


def test_converted_designs_draw_under_api_v2(converted: Path) -> None:
    svgs = converted / "svg"
    done = subprocess.run(
        [sys.executable, SMOKE, converted / "out", "--svg-dir", svgs, "--jobs", "2"]
        + ["--json", converted / "smoke.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    status = {r["slug"]: r for r in json.loads((converted / "smoke.json").read_text())}
    for name in ("basic", "pixels", "seeded", "v1_walldye"):
        assert status[name]["status"] == "ok", status[name]
        assert (svgs / f"{name}.svg").read_text().startswith("<svg")
    # the raw clip markup and the fmt() string paths are left for the port agent
    assert status["groups"]["status"] == "draw"
    assert "clip()" in str(status["groups"]["error"])
    assert status["colours"]["status"] == "draw"

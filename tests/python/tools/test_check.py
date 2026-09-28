import json
import os
import shutil
import subprocess
import sys

import pytest
from fixtures import regen
from tools_support import built, legacy, versions

from walldye import _basis
from walldye.tools import build, check, common, hashing

TEXT_SOURCE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">\n'
    '<defs><filter id="soft"><feGaussianBlur stdDeviation="2"/></filter></defs>\n'
    '<rect x="0" y="0" width="1920" height="1080" fill="#1C1B1A" filter="url(#soft)"/>\n'
    '<text x="10" y="50" fill="#CF6A4C">hello</text>\n</svg>\n'
)
MASKED_SOURCE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">\n'
    '<defs><mask id="m1"><rect width="1920" height="1080" fill="#DAD8CE"/></mask></defs>\n'
    '<rect x="0" y="0" width="1920" height="1080" fill="#1C1B1A" mask="url(#m1)"/>\n</svg>\n'
)


def report(slug: str, **kw) -> check.Report:
    """check.run's report for one piece, without printing."""
    t = check.prepare(slug, kw.pop("variant", None))
    check.lint_source(t)
    check.source_checks([t])
    for v in t.variants:
        t.report.add(
            check.check_variant(check.Task(str(common.WALLPAPERS), slug, v, t.regimes, **kw))
        )
    if t.piece is not None:
        check.siblings(
            t.report, t.piece.variant_names(), {v: r.ink for v, r in t.report.results.items()}
        )
    return t.report


@pytest.mark.parametrize("design", ["collision", "mask", "keyed", "light-branch", "versions"])
def test_clean_designs_pass(wallpapers, design):
    if design == "versions":
        versions(wallpapers)
    else:
        regen.install(wallpapers, design)
    r = report(design)
    assert r.errors == [] and r.notes == []


def test_data_design_reads_its_files(wallpapers):
    regen.install(wallpapers, "data", data={"points.json": "[[960, 540], [1200, 300]]\n"})
    assert report("data").errors == []
    (wallpapers / "data/data/extra.csv").write_text("x\n")
    (wallpapers / "data/data/sub").mkdir()
    assert report("data").errors == [
        "data/extra.csv: data files are .json, .txt or .npy with a plain name",
        "data/sub/: data/ holds files only, no subdirectories",
    ]


@pytest.mark.parametrize(
    ("design", "expected"),
    [
        ("unseeded", "16:9 dark: two draws differ"),
        ("unseeded", "line 3: imports random"),
        ("hash-order", "a fresh process with PYTHONHASHSEED=4242 draws it differently"),
        ("rounding", "held-out themes miss by more than 2 units"),
    ],
)
def test_check_catches(wallpapers, design, expected):
    regen.install(wallpapers, design)
    errors = report(design).errors
    assert any(expected in e for e in errors), errors


def test_determinism_failure_stops_before_geometry(wallpapers):
    regen.install(wallpapers, "unseeded")
    result = check.check_variant(
        check.Task(str(wallpapers), "unseeded", "default", ("dark", "light"))
    )
    assert result.errors and all("two draws differ" in e for e in result.errors)
    assert result.templates == {} and result.entries == {} and result.ink is None


def test_legacy_backstops(wallpapers):
    legacy(wallpapers, "texty", source=TEXT_SOURCE, palette='"#1C1B1A": bg\n"#CF6A4C": accent\n')
    errors = report("texty").errors
    assert (
        "16x9.svg: <text> depends on installed fonts; draw glyphs as paths (walldye.pixel)"
        in errors
    )
    assert "16x9.svg: <filter> is not allowed: slow at 4K, soft, and renderers disagree" in errors
    legacy(wallpapers, "masked", source=MASKED_SOURCE, palette='"#1C1B1A": bg\n"#DAD8CE": fg\n')
    errors = report("masked").errors
    assert any(
        "16:9 dark: theme-dependent #DAD8CE ×1 in mask content (line 2)" in e for e in errors
    )


def test_design_exception_names_the_line(wallpapers):
    regen.install(wallpapers, "collision")
    design = wallpapers / "collision/design.py"
    design.write_text(
        design.read_text().replace(
            "    s.fill(P().rect(0, 0", '    raise KeyError("nope")\n    s.fill(P().rect(0, 0'
        )
    )
    assert report("collision").errors == [
        "16:9 dark: draw failed: KeyError: 'nope' (design.py line 8)"
    ]


def test_import_errors_are_reported(wallpapers):
    regen.install(wallpapers, "collision")
    (wallpapers / "collision/design.py").write_text('"""Old."""\n\n\ndef draw(s):\n    pass\n')
    errors = report("collision").errors
    assert (
        "import failed: ValueError: design.py must define @design(...) def draw(s: Canvas[...]) -> None"
        in errors
    )
    assert any("line 4: a design has exactly one module-level @design" in e for e in errors)


def test_ruff_and_pyrefly_findings(wallpapers):
    regen.install(wallpapers, "collision")
    design = wallpapers / "collision/design.py"
    text = design.read_text().replace(
        "from walldye import BLACK", "import math\nfrom walldye import BLACK"
    )
    design.write_text(text.replace("s.w / 2, s.h), UI_HI)", "s.w / 2, s.h), UI_HI, rule='odd')"))
    errors = report("collision").errors
    assert (
        "ruff format: the file would be reformatted (run uv run ruff format " + str(design) + ")"
        in errors
    )
    assert "line 3: ruff F401: `math` imported but unused" in errors
    assert any(
        e.startswith("line 9: pyrefly [bad-argument-type]: Argument `Literal['odd']`")
        and e.endswith("in function `walldye.Canvas.fill`")
        for e in errors
    )


def test_pyrefly_messages_keep_the_reason_and_the_closest_overload(wallpapers):
    versions(wallpapers)
    design = wallpapers / "versions/design.py"
    design.write_text(design.read_text().replace("bearing=p.hour * 30", "p.hour * 30"))
    errors = report("versions").errors
    assert (
        "line 21: pyrefly [no-matching-overload]: No matching overload found for function"
        " `walldye.polar` called with arguments: (Vec, float, float); closest overload"
        " (c: tuple[float | floating | integer, float | floating | integer], r: Num, *,"
        " deg: Num) -> Vec; Expected at most 2 positional arguments, got 3"
    ) in errors


def test_a_design_that_fails_to_import_still_gets_ruff_and_pyrefly(wallpapers, capsys):
    versions(wallpapers)
    design = wallpapers / "versions/design.py"
    text = design.read_text().replace('"late": Clock(hour=8)', '"late": Clock(hour="8")')
    design.write_text("import math\n" + text.replace("bearing=p.hour * 30", "p.hour * 30"))
    errors = report("versions").errors
    assert any(e.startswith("import failed: TypeError: Clock.hour takes") for e in errors)
    assert "line 1: ruff F401: `math` imported but unused" in errors
    assert any("pyrefly [bad-argument-type]: Argument `Literal['8']`" in e for e in errors)
    assert any("pyrefly [no-matching-overload]" in e for e in errors)
    assert build.run(["versions"], jobs=1) == 1
    out = capsys.readouterr().out
    assert (
        "ruff F401: `math` imported but unused" in out and "pyrefly [no-matching-overload]" in out
    )


def test_missing_tools_are_errors(wallpapers, monkeypatch):
    regen.install(wallpapers, "collision")
    design = wallpapers / "collision/design.py"
    beside = common.tool("ruff")
    assert beside is not None
    monkeypatch.setattr(sys, "executable", str(wallpapers / "nowhere/python"))
    # uv run --with: sys.executable is an overlay without the tools, the project's bin on PATH
    monkeypatch.setenv("PATH", str(beside.parent))
    assert common.tool("ruff") == beside
    assert check.tool_findings([design]) == {design.resolve(): []}
    monkeypatch.setenv("PATH", str(wallpapers / "nowhere"))
    assert check.tool_findings([design]) == {
        design.resolve(): [
            "ruff format: ruff not found; run walldye through uv run",
            "ruff check: ruff not found; run walldye through uv run",
            "pyrefly: pyrefly not found; run walldye through uv run",
        ]
    }


def test_tool_output_it_cannot_read_fails_every_file(wallpapers, monkeypatch):
    regen.install(wallpapers, "collision")
    regen.install(wallpapers, "mask")
    paths = [wallpapers / "collision/design.py", wallpapers / "mask/design.py"]
    outputs = iter(["Traceback: boom", '{"errors": 3}', "[]"])

    def fake(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 2, stdout=next(outputs), stderr="")

    monkeypatch.setattr(check.subprocess, "run", fake)
    assert check.tool_findings(paths) == {
        p.resolve(): [
            "ruff format failed: Traceback: boom",
            "ruff check printed no list of findings",
        ]
        for p in paths
    }


def test_determinism_subprocess_failures_are_errors(wallpapers, monkeypatch):
    regen.install(wallpapers, "hash-seed")
    task = check.Task(str(wallpapers), "hash-seed", "default", ("dark",))
    (error,) = check.check_variant(task).errors
    assert error.startswith("determinism subprocess failed: ")
    assert error.endswith("RuntimeError: only in the determinism subprocess")
    for stdout, want in (("[1]", "printed '[1]'"), ("oops", "printed 'oops'")):
        monkeypatch.setattr(
            check.subprocess,
            "run",
            lambda cmd, stdout=stdout, **kw: subprocess.CompletedProcess(cmd, 0, stdout, ""),
        )
        assert check._fresh_process({"k": "sha"}) == [f"determinism subprocess {want}"]


def test_paranoid_reports_a_failing_fresh_import(wallpapers, monkeypatch):
    regen.install(wallpapers, "collision")

    def gone(slug):
        raise ImportError(f"{slug} is gone")

    monkeypatch.setattr(common, "fresh", gone)
    task = check.Task(str(wallpapers), "collision", "default", ("dark",), paranoid=True)
    assert check.check_variant(task).errors == [
        "fresh import failed: ImportError: collision is gone"
    ]


def test_paranoid_catches_leaked_module_state(wallpapers):
    regen.install(wallpapers, "leaky")
    assert report("leaky").errors == []
    errors = report("leaky", paranoid=True).errors
    assert len(errors) == 2 and all("a fresh import drawn for" in e for e in errors)
    assert errors[0].startswith("10:16 dark: a fresh import drawn for fireproof differs")


def test_sibling_rule(wallpapers):
    versions(wallpapers)
    design = wallpapers / "versions/design.py"
    design.write_text(
        design.read_text().replace('"late": Clock(hour=8)', '"late": Clock(hour=2.05)')
    )
    errors = report("versions").errors
    assert len(errors) == 1
    assert errors[0].startswith("versions default and late look alike (ink-map cosine 0.9")
    assert errors[0].endswith("must be below 0.93): a variant must change what is depicted")


@pytest.mark.parametrize("bg", ["BG_DEEP", "MUTED"])
def test_sibling_rule_measures_from_the_designs_own_background(wallpapers, bg):
    versions(wallpapers)
    design = wallpapers / "versions/design.py"
    text = design.read_text().replace("import ACCENT,", f"import ACCENT, {bg},")
    design.write_text(text.replace("variants=VARIANTS)", f"variants=VARIANTS, bg={bg})"))
    r = report("versions")
    assert r.errors == []
    # the disc sits at two o'clock, up and right of the centre a counted background pulls to
    fx, fy = r.results["default"].focus
    assert fx > 0.6 and fy < 0.4


def test_one_variant_is_compared_with_committed_siblings(wallpapers, capsys):
    versions(wallpapers)
    r = report("versions", variant="late")
    assert r.errors == [] and list(r.results) == ["late"]
    assert r.notes == [
        "default is not built yet, so the other versions were not compared with it",
        "bare is not built yet, so the other versions were not compared with it",
    ]
    built(capsys, "versions")
    design = wallpapers / "versions/design.py"
    design.write_text(
        design.read_text().replace('"late": Clock(hour=8)', '"late": Clock(hour=2.05)')
    )
    r = report("versions", variant="late")
    assert r.notes == [] and len(r.errors) == 1 and "default and late look alike" in r.errors[0]
    with pytest.raises(common.UsageError, match="has no variant 'early'"):
        check.prepare("versions", "early")
    # an old clash between two other versions is not this variant's to fix
    shutil.copy(common.build_dir("versions") / "16x9.svg", common.build_dir("versions", "bare"))
    design.write_text(
        design.read_text().replace('"late": Clock(hour=2.05)', '"late": Clock(hour=8)')
    )
    assert report("versions", variant="late").errors == []
    assert report("versions").errors == []


def test_variant_values_outside_soft_ranges_warn(wallpapers, capsys):
    versions(wallpapers)
    design = wallpapers / "versions/design.py"
    design.write_text(design.read_text().replace('"late": Clock(hour=8)', '"late": Clock(hour=-4)'))
    r = report("versions")
    assert r.errors == [] and r.warnings == ["late: hour=-4 is outside 0..12"]
    assert report("versions", variant="bare").warnings == []
    assert check.run(["versions"], variant="late", jobs=1) == 0
    assert "  warning: late: hour=-4 is outside 0..12" in capsys.readouterr().out.splitlines()


def test_variants_need_meta_labels(wallpapers):
    regen.install(wallpapers, "versions")
    assert check.prepare("versions").report.errors == [
        "meta.yaml needs variants: with a label for each of default, late, bare"
    ]
    versions(wallpapers)
    assert check.prepare("versions").report.errors == []


def test_slow_variants_warn(wallpapers, monkeypatch):
    regen.install(wallpapers, "collision")
    monkeypatch.setattr(check, "SLOW", 0.0)
    result = check.check_variant(check.Task(str(wallpapers), "collision", "default", ("dark",)))
    assert result.warnings[-1].startswith("the check took") and result.warnings[-1].endswith(
        "over 0 s"
    )


def test_pixel_grids_give_cells_and_origin_warnings(wallpapers):
    regen.install(wallpapers, "pixels")
    result = check.check_variant(
        check.Task(str(wallpapers), "pixels", "default", ("dark", "light"))
    )
    assert result.errors == [] and result.cells == [3.0]
    assert (
        "16:9: pixel grid origin (710.4, 442.8) is not a whole unit; snap it to the 3-unit cell grid"
        in result.warnings
    )
    assert len(result.entries) == 12 and len(result.templates) == 6


def test_hashes_subprocess(wallpapers):
    regen.install(wallpapers, "versions")
    keys = ["versions@late@10:16@light", "versions@default@16:9@dark"]
    run = subprocess.run(
        [sys.executable, "-m", "walldye", "_hashes", str(wallpapers), *keys],
        env={**os.environ, "PYTHONHASHSEED": "1"}, capture_output=True, text=True, check=True,
    )  # fmt: skip
    got = json.loads(run.stdout)
    assert list(got) == keys
    piece = common.load("versions")
    for k in keys:
        _, variant, aspect, regime = k.split("@")
        from walldye._design import RenderSpec

        doc = common.draw(piece, RenderSpec(variant, piece.params(variant), aspect, regime))
        want = doc.to_svg(common.tokens_of(_basis.BASIS[regime][0]))
        assert got[k] == hashing.sha256(want.encode())


def test_run_codes_and_similar(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    regen.install(wallpapers, "collision", "copy")
    regen.install(wallpapers, "mask")
    built(capsys, "collision", "copy")
    assert check.run(["copy", "mask"], similar=True, jobs=1) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[-3:] == [
        "similar (1.00): collision ~ copy",
        "similar: skipped, no build/16x9.svg: mask",
        "2/2 ok",
    ]
    assert check.run([]) == 2
    assert check.run(["missing"]) == 1
    assert "missing: 1 error(s)" in capsys.readouterr().out


def test_pool_matches_one_process(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    versions(wallpapers)
    assert check.run(["collision", "versions"], jobs=1) == 0
    alone = capsys.readouterr().out
    assert check.run(["collision", "versions"], jobs=2) == 0
    assert capsys.readouterr().out == alone
    assert alone.splitlines() == ["collision: ok", "versions: ok", "2/2 ok"]


def test_meta_yaml_problems(wallpapers):
    regen.install(wallpapers, "collision")
    meta = wallpapers / "collision/meta.yaml"
    meta.write_text("- a\n- b\n")
    assert report("collision").errors == [f"{meta}: must be a mapping"]
    meta.write_text("title: [x\n")
    assert report("collision").errors == [
        f"{meta}: not valid YAML (line 2): expected ',' or ']', but got '<stream end>'"
    ]

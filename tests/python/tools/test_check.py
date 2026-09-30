import json
import os
import subprocess
import sys

import pytest
from fixtures import pieces
from tools_support import built, legacy, versions

from walldye.tools import check, common, hashing, themes

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
    for v in t.variants:
        t.report.add(check.check_variant(check.Task(str(common.WALLPAPERS), slug, v, **kw)))
    return t.report


@pytest.mark.parametrize("design", ["collision", "mask", "keyed", "light-branch", "versions"])
def test_clean_designs_pass(wallpapers, design):
    if design == "versions":
        versions(wallpapers)
    else:
        pieces.install(wallpapers, design)
    r = report(design)
    assert r.errors == [] and r.notes == []


def test_data_design_reads_its_files(wallpapers):
    pieces.install(wallpapers, "data", data={"points.json": "[[960, 540], [1200, 300]]\n"})
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
    pieces.install(wallpapers, design)
    errors = report(design).errors
    assert any(expected in e for e in errors), errors


def test_determinism_failure_stops_before_geometry(wallpapers):
    pieces.install(wallpapers, "unseeded")
    result = check.check_variant(check.Task(str(wallpapers), "unseeded", "default"))
    assert result.errors and all("two draws differ" in e for e in result.errors)
    assert result.templates == {} and result.entries == {} and result.focus is None


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
    pieces.install(wallpapers, "collision")
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
    pieces.install(wallpapers, "collision")
    (wallpapers / "collision/design.py").write_text('"""Old."""\n\n\ndef draw(s):\n    pass\n')
    errors = report("collision").errors
    assert (
        "import failed: ValueError: design.py must define @design(...) def draw(s: Canvas[...]) -> None"
        in errors
    )
    assert any("line 4: a design has exactly one module-level @design" in e for e in errors)


def test_determinism_subprocess_failures_are_errors(wallpapers):
    pieces.install(wallpapers, "hash-seed")
    task = check.Task(str(wallpapers), "hash-seed", "default")
    (error,) = check.check_variant(task).errors
    assert error.startswith("determinism subprocess failed: ")
    assert error.endswith("RuntimeError: only in the determinism subprocess")
    for stdout, want in (("[1]", "printed '[1]'"), ("oops", "printed 'oops'")):
        run = subprocess.CompletedProcess([], 0, stdout, "")
        assert check._fresh_errors(run, {"k": "sha"}) == [f"determinism subprocess {want}"]


def test_a_design_error_stops_the_determinism_subprocess(wallpapers, monkeypatch):
    pieces.install(wallpapers, "hash-seed")
    started = []

    def start(keys):
        started.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]))
        return started[-1]

    def boom(piece, spec):
        raise check.DesignError("boom")

    monkeypatch.setattr(check, "_start_fresh", start)
    monkeypatch.setattr(check, "draw", boom)
    assert check.check_variant(check.Task(str(wallpapers), "hash-seed", "default")).errors == [
        "boom"
    ]
    assert started[0].returncode is not None


def test_paranoid_reports_a_failing_fresh_import(wallpapers, monkeypatch):
    pieces.install(wallpapers, "collision")

    def gone(slug):
        raise ImportError(f"{slug} is gone")

    monkeypatch.setattr(common, "fresh", gone)
    task = check.Task(str(wallpapers), "collision", "default", paranoid=True)
    assert check.check_variant(task).errors == [
        "fresh import failed: ImportError: collision is gone"
    ]


def test_paranoid_catches_leaked_module_state(wallpapers):
    pieces.install(wallpapers, "leaky")
    assert report("leaky").errors == []
    errors = report("leaky", paranoid=True).errors
    assert len(errors) == 2 and all("a fresh import drawn for" in e for e in errors)
    assert errors[0].startswith("10:16 dark: a fresh import drawn for fireproof differs")


@pytest.mark.parametrize("bg", ["BG_DEEP", "MUTED"])
def test_focus_is_measured_from_the_designs_own_background(wallpapers, bg):
    versions(wallpapers)
    design = wallpapers / "versions/design.py"
    text = design.read_text().replace("import ACCENT,", f"import ACCENT, {bg},")
    design.write_text(text.replace("variants=VARIANTS)", f"variants=VARIANTS, bg={bg})"))
    r = report("versions")
    assert r.errors == []
    # the disc sits at two o'clock, up and right of the center a counted background pulls to
    fx, fy = r.results["default"].focus
    assert fx > 0.6 and fy < 0.4


def test_one_variant_is_checked_alone(wallpapers):
    versions(wallpapers)
    r = report("versions", variant="late")
    assert r.errors == [] and r.notes == [] and list(r.results) == ["late"]
    with pytest.raises(common.UsageError, match="has no variant 'early'"):
        check.prepare("versions", "early")


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
    pieces.install(wallpapers, "versions")
    assert check.prepare("versions").report.errors == [
        "meta.yaml needs variants: with a label for each of default, late, bare"
    ]
    versions(wallpapers)
    assert check.prepare("versions").report.errors == []


def test_slow_variants_warn(wallpapers, monkeypatch):
    pieces.install(wallpapers, "collision")
    monkeypatch.setattr(check, "SLOW", 0.0)
    result = check.check_variant(check.Task(str(wallpapers), "collision", "default"))
    assert result.warnings[-1].startswith("the check took") and result.warnings[-1].endswith(
        "over 0 s"
    )


def test_pixel_grids_give_cells_and_origin_warnings(wallpapers):
    pieces.install(wallpapers, "pixels")
    result = check.check_variant(check.Task(str(wallpapers), "pixels", "default"))
    assert result.errors == [] and result.cells == [3.0]
    assert (
        "16:9: pixel grid origin (710.4, 442.8) is not a whole unit; snap it to the 3-unit cell grid"
        in result.warnings
    )
    assert len(result.entries) == 12 and len(result.templates) == 6


def test_hashes_subprocess(wallpapers):
    pieces.install(wallpapers, "versions")
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
        want = doc.to_svg(themes.tokens_of(themes.SAMPLE[regime]))
        assert got[k] == hashing.sha256(want.encode())


def test_run_codes_and_similar(wallpapers, capsys):
    pieces.install(wallpapers, "collision")
    pieces.install(wallpapers, "collision", "copy")
    pieces.install(wallpapers, "mask")
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
    pieces.install(wallpapers, "collision")
    versions(wallpapers)
    assert check.run(["collision", "versions"], jobs=1) == 0
    alone = capsys.readouterr().out
    assert check.run(["collision", "versions"], jobs=2) == 0
    assert capsys.readouterr().out == alone
    assert alone.splitlines() == ["collision: ok", "versions: ok", "2/2 ok"]


def test_meta_yaml_problems(wallpapers):
    pieces.install(wallpapers, "collision")
    meta = wallpapers / "collision/meta.yaml"
    meta.write_text("- a\n- b\n")
    assert report("collision").errors == [f"{meta}: must be a mapping"]
    meta.write_text("title: [x\n")
    assert report("collision").errors == [
        f"{meta}: not valid YAML (line 2): expected ',' or ']', but got '<stream end>'"
    ]

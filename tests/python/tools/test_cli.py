import datetime
import json
import shutil

import pytest
from PIL import Image
from tools_support import built, legacy, versions

from walldye._aspect import SITE_ASPECTS
from walldye._theme import PRESETS, TOKENS, derive_theme, parse_seeds, parse_theme
from walldye.tools import build, check, cli, common, listing, new, preview, review, sheet

# A ring everywhere; the dot only in the light regime, so light geometry differs.
TINY = '''"""A ring with a dot that only the light version draws."""

from walldye import ACCENT, UI, Canvas, P, design


@design(aspects="any")
def draw(s: Canvas) -> None:
    s.stroke(P().circle(s.center, 200), UI, 2)
    if s.light:
        s.fill(P().circle(s.center, 20), ACCENT)
'''
FLAT = '''"""A square."""

from walldye import UI, Canvas, P, design


@design()
def draw(s: Canvas) -> None:
    s.fill(P().rect(10, 10, 100, 100), UI)
'''


def piece(wallpapers, slug, design=TINY, **meta):
    d = wallpapers / slug
    d.mkdir()
    (d / "design.py").write_text(design)
    fields = {
        "title": slug.capitalize(),
        "description": "A test piece.",
        "model": "claude-opus-5-5",
    }
    new.write_meta(slug, {**fields, "draft": True, **meta})
    return d


def meta(slug):
    return common.load_meta(slug)


# --- new -----------------------------------------------------------------------


def test_new_scaffolds_a_draft(wallpapers, capsys):
    args = ["new", "ring-one", "--model", "claude-opus-5-5"]
    assert cli.main(args) == 0
    d = wallpapers / "ring-one"
    assert capsys.readouterr().out.strip() == str(d)
    text = (d / "meta.yaml").read_text()
    assert "license" not in text
    assert "technique: []\n" in text and "proposed_facets: {}\n" in text
    m = meta("ring-one")
    assert m["draft"] is True and m["model"] == "claude-opus-5-5" and "author" not in m
    assert m["added"] == datetime.datetime.now().astimezone().date()
    assert (d / "design.py").read_text() == new.DESIGN
    assert "A240 240" in common.render("ring-one", "nord")
    assert common.load("ring-one").aspects == ("16:9",)
    # The template passes the design lint as written.
    t = check.prepare("ring-one")
    check.lint_source(t)
    assert t.report.errors == ["meta.yaml needs a description"]


@pytest.mark.parametrize(
    "slug", ["about", "sitemap-index", "og", "Bad_Slug", "-x", "a--b", "taken"]
)
def test_new_refuses(wallpapers, slug):
    (wallpapers / "taken").mkdir()
    with pytest.raises(SystemExit) as e:
        new.run(slug, "m")
    assert e.value.code not in (0, None)


def test_meta_yaml_round_trips_in_house_style(wallpapers):
    piece(wallpapers, "styled", notes="Line one.\n\nLine two.\n", technique=["drafting", "weave"],
          sources=[{"kind": "recreation", "title": "Schotter", "year": 1968}])  # fmt: skip
    text = (wallpapers / "styled/meta.yaml").read_text()
    assert "notes: |\n  Line one.\n\n  Line two.\n" in text
    assert "technique: [drafting, weave]\n" in text
    assert "sources:\n  - kind: recreation\n    title: Schotter\n    year: 1968\n" in text
    assert meta("styled")["notes"] == "Line one.\n\nLine two.\n"


# --- render ----------------------------------------------------------------------


def test_render_names_file_after_slug_variant_token_and_aspect(
    wallpapers, tmp_path, monkeypatch, capsys
):
    piece(wallpapers, "tiny")
    versions(wallpapers)
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(out)
    assert cli.main(["render", "tiny", "--theme", "2E3440-ECEFF4-88C0D0", "--aspect", "21:9"]) == 0
    assert capsys.readouterr().out.strip() == "tiny-nord-21x9.svg"
    text = (out / "tiny-nord-21x9.svg").read_text()
    assert text == common.render("tiny", "nord", "21:9") and 'viewBox="0 0 2520 1080"' in text

    assert cli.main(["render", "versions", "--variant", "late", "--theme", "flexoki-light"]) == 0
    assert capsys.readouterr().out.strip() == "versions--late-flexoki-light-16x9.svg"
    assert (out / "versions--late-flexoki-light-16x9.svg").read_text() == common.render(
        "versions", "flexoki-light", variant="late"
    )

    args = ["render", "tiny", "--theme", "1c1b1b-dad8ce-cf6a4c", "--crop", "100,50,400,300"]
    assert cli.main(args) == 0
    cropped = (out / "tiny-1c1b1b-dad8ce-cf6a4c-16x9-crop.svg").read_text()
    assert cropped.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="100 50 400 300" width="400" height="300">'
    )
    capsys.readouterr()
    assert cli.main(["render", "tiny", "-o", "-"]) == 0
    assert capsys.readouterr().out == common.render("tiny", "fireproof")
    assert cli.main(["render", "tiny", "-o", "new/dir/tiny.svg"]) == 0
    assert (out / "new/dir/tiny.svg").exists()


def test_render_to_stdout_keeps_design_prints_out(wallpapers, capsys):
    piece(wallpapers, "chatty", TINY.replace("-> None:\n", "-> None:\n    print('debug')\n"))
    assert cli.main(["render", "chatty", "-o", "-"]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("<svg") and captured.err == "debug\n"


def test_render_theme_from_env(wallpapers, tmp_path, monkeypatch):
    piece(wallpapers, "tiny")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WALLDYE_THEME", "flexoki-light")
    assert cli.main(["render", "tiny"]) == 0
    assert (tmp_path / "tiny-flexoki-light-16x9.svg").exists()
    monkeypatch.setenv("WALLDYE_THEME", "nord,accent=#D08770")
    with pytest.raises(SystemExit) as e:
        cli.main(["render", "tiny"])
    assert e.value.code == 2


def test_render_refuses_build_dirs_and_undeclared_aspects(wallpapers, tmp_path):
    piece(wallpapers, "tiny")
    piece(wallpapers, "flat", FLAT)
    (wallpapers / "tiny/build").mkdir()
    with pytest.raises(SystemExit, match="only walldye build"):
        cli.main(["render", "tiny", "-o", str(wallpapers / "tiny/build/16x9.svg")])
    assert not (wallpapers / "tiny/build/16x9.svg").exists()
    with pytest.raises(SystemExit, match=r"declares aspects=\('16:9',\), not 21:9"):
        cli.main(["render", "flat", "--aspect", "21:9", "-o", str(tmp_path / "x.svg")])
    for bad in (
        ["render", "nope"],
        ["render", "tiny", "--aspect", "wide"],
        ["render", "tiny", "--aspect", "inf:1"],
        ["render", "tiny", "--aspect", "16:-9"],
        ["render", "tiny", "--crop", "1,2,3"],
        ["preview", "tiny", "--width", "0"],
        ["sheet", "--all", "--cols", "0"],
        ["sheet", "--all", "--thumb", "-5"],
        ["check", "--all", "--jobs", "0"],
    ):
        with pytest.raises(SystemExit) as e:
            cli.main(bad)
        assert e.value.code == 2


def test_render_fit_cuts_undeclared_aspects_from_16_9(wallpapers, capsys):
    piece(wallpapers, "tiny")
    piece(wallpapers, "flat", FLAT)
    # The square sits top left, so both crops clamp to that corner.
    assert cli.main(["render", "flat", "--aspect", "21:9", "--fit", "-o", "-"]) == 0
    assert capsys.readouterr().out.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 822.857"'
        ' width="1920" height="822.857">'
    )
    assert cli.main(["render", "flat", "--aspect", "9:19.5", "--fit", "-o", "-"]) == 0
    assert 'viewBox="0 0 498.462 1080"' in capsys.readouterr().out
    # A declared aspect is drawn for, not cut.
    assert cli.main(["render", "tiny", "--aspect", "21:9", "--fit", "-o", "-"]) == 0
    assert capsys.readouterr().out == common.render("tiny", "fireproof", "21:9")
    with pytest.raises(SystemExit) as e:
        cli.main(["render", "flat", "--aspect", "21:9", "--fit", "--crop", "0,0,10,10"])
    assert e.value.code == 2


def test_render_png_at_exact_pixel_sizes(wallpapers, tmp_path):
    piece(wallpapers, "tiny")
    piece(wallpapers, "flat", FLAT)
    for args, size in (
        (["tiny", "--aspect", "3440x1440", "--width", "3440"], (3440, 1440)),
        (["tiny", "--aspect", "21:9"], (2520, 1080)),
        # 1080 / 2340 of the 16:9 canvas is 498.46 wide: the rounding must not cost a pixel.
        (["flat", "--aspect", "1080x2340", "--fit", "--width", "1080"], (1080, 2340)),
        (["flat", "--aspect", "3440x1440", "--fit", "--width", "3440"], (3440, 1440)),
    ):
        out = tmp_path / "wall.png"
        assert cli.main(["render", *args, "-o", str(out)]) == 0
        with Image.open(out) as img:
            assert (img.size, img.mode) == (size, "RGB")
    with pytest.raises(SystemExit) as e:
        cli.main(["render", "tiny", "--width", "100", "-o", str(tmp_path / "x.svg")])
    assert e.value.code == 2


def test_fit_crop_centers_on_the_focus_within_the_canvas():
    assert common.fit_crop("16:9", (0.1, 0.9)) == (0.0, 0.0, 1920.0, 1080.0)
    x, y, w, h = common.fit_crop("21:9", (0.5, 1.0))
    assert (x, w) == (0.0, 1920.0) and h == pytest.approx(822.857, abs=1e-3)
    assert y == pytest.approx(1080 - h)
    x, y, w, h = common.fit_crop("9:19.5", (0.5, 0.5))
    assert (y, h) == (0.0, 1080.0) and x == pytest.approx((1920 - w) / 2)


# --- preview ----------------------------------------------------------------------


def test_preview_writes_png_and_reports(wallpapers, tmp_path, monkeypatch, capsys):
    piece(wallpapers, "tiny")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path / "prev"))
    args = ["preview", "tiny", "--theme", "flexoki-light", "--aspect", "9:19.5", "--width", "400"]
    assert cli.main(args) == 0
    lines = capsys.readouterr().out.splitlines()
    png = tmp_path / "prev/tiny-flexoki-light-9x19.5.png"
    assert lines == [
        "lint: ok",
        "regime: light (flexoki-light)",
        "light geometry: differs from dark (build writes a light template for each native aspect)",
        str(png),
    ]
    assert Image.open(png).size == (185, 401)  # --width is the long side, up to rounding
    assert cli.main(["preview", "tiny", "--crop", "0,0,300,600", "--width", "300"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert Image.open(lines[-1]).size == (150, 300)
    assert lines[-1].endswith("tiny-fireproof-16x9-crop-0-0-300-600.png")
    assert "regime: dark (fireproof)" in lines


def test_preview_prints_lint_lines(wallpapers, tmp_path, monkeypatch, capsys):
    design = TINY.replace("from walldye import", "import random\n\nfrom walldye import").replace(
        "    if s.light:",
        "    # a crimson rim\n    s.pixel_path(P().rect(0.5, 3, 4, 4), UI, cell=4, origins=[(0.5, 3)])\n    if s.light:",
    )
    piece(wallpapers, "loud", design, description="A crimson disc.")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "loud", "--theme", "nord", "--width", "64"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("error: line 3: imports random;")
    assert lines[1:4] == [
        "warning: color words in docstrings or comments: crimson (name tokens or roles, never hues)",
        "warning: color words in meta.yaml copy: crimson (describe the shape or what it picks out, without naming colors)",
        "warning: pixel grid origin (0.5, 3) is not a whole unit; snap it to the 4-unit cell grid",
    ]
    assert lines[4] == "lint: 1 error(s), 3 warning(s)"


def test_preview_undeclared_aspect(wallpapers, tmp_path, monkeypatch, capsys):
    piece(wallpapers, "flat", FLAT)
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "flat", "--aspect", "21:9", "--width", "200"]) == 0
    out = capsys.readouterr().out
    assert "warning: flat declares aspects=('16:9',); rendered 21:9 anyway" in out
    assert "light geometry: same as dark" in out


def test_preview_legacy_piece(wallpapers, tmp_path, monkeypatch, capsys):
    legacy(wallpapers)
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "old", "--theme", "nord", "--width", "64"]) == 0
    assert capsys.readouterr().out.splitlines()[:3] == [
        "lint: ok",
        "regime: dark (nord)",
        "light geometry: same as dark (one template serves both regimes)",
    ]


def test_lint_checks_the_viewbox(wallpapers):
    piece(wallpapers, "tiny")
    svg = common.render("tiny", "fireproof")
    assert preview.lint("tiny", svg, "16:9", []) == ([], [])
    assert preview.lint("tiny", svg, "21:9", [])[0] == ['viewBox is not "0 0 2520 1080"']


def test_crop_parsing():
    assert preview.parse_crop("1,2.5,3,4") == (1, 2.5, 3, 4)
    for bad in ("1,2,3", "1,2,0,4", "a,b,c,d", "1,2,3,-4"):
        with pytest.raises(ValueError):
            preview.parse_crop(bad)


# --- check / build wiring --------------------------------------------------------------


def test_check_and_build_wiring(wallpapers, monkeypatch):
    piece(wallpapers, "tiny")
    checks, builds = [], []
    monkeypatch.setattr(check, "run", lambda slugs, **kw: checks.append((slugs, kw)) or 3)
    monkeypatch.setattr(build, "run", lambda slugs, **kw: builds.append((slugs, kw)) or 0)
    assert cli.main(["check", "tiny", "--similar", "--variant", "late", "--jobs", "2"]) == 3
    assert cli.main(["check", "--all", "--paranoid"]) == 3
    assert checks == [
        (
            ["tiny"],
            {"all": False, "variant": "late", "paranoid": False, "similar": True, "jobs": 2},
        ),
        ([], {"all": True, "variant": None, "paranoid": True, "similar": False, "jobs": None}),
    ]
    assert cli.main(["build", "tiny", "--force", "--variant", "late"]) == 0
    assert cli.main(["build", "--all", "--published", "--jobs", "4"]) == 0
    assert builds == [
        (
            ["tiny"],
            {"all": False, "force": True, "variant": "late", "published": False, "jobs": None},
        ),
        ([], {"all": True, "force": False, "variant": None, "published": True, "jobs": 4}),
    ]
    for bad in (
        ["check"],
        ["check", "--all", "tiny"],
        ["build"],
        ["sheet"],
        ["check", "missing"],
        ["check", "Bad"],
    ):
        with pytest.raises(SystemExit) as e:
            cli.main(bad)
        assert e.value.code == 2


def test_hashes_hands_off_to_check(monkeypatch):
    seen = []
    monkeypatch.setattr(check, "hashes_main", lambda args: seen.append(args) or 0)
    assert cli.main(["_hashes", "/w", "tiny@default@16:9@dark", "tiny@late@9:19.5@light"]) == 0
    assert seen == [["/w", "tiny@default@16:9@dark", "tiny@late@9:19.5@light"]]
    assert "_hashes" not in cli._parser().format_help()


# --- list / themes -----------------------------------------------------------------------


def test_list(wallpapers, capsys):
    piece(wallpapers, "tiny", title="Tiny\tring", description="A ring,\n  drawn once.")
    piece(wallpapers, "flat", FLAT, draft=False)
    versions(wallpapers)
    assert cli.main(["list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "flat\tFlat\tA test piece.\t-\t16:9\t",
        f"tiny\tTiny ring\tA ring, drawn once.\tdraft\t{','.join(SITE_ASPECTS)}\t",
        "versions\tFixture\tA synthetic design for the build tests.\tdraft\t16:9,10:16\tlate,bare",
    ]


def test_themes_fixture(capsys):
    assert cli.main(["themes"]) == 0
    assert "fireproof          #1C1B1A #DAD8CE #CF6A4C  dark (default)" in capsys.readouterr().out
    fx = listing.fixture()
    assert list(fx["presets"]) == list(PRESETS)
    assert fx["presets"]["fireproof"]["tokens"] == PRESETS["fireproof"]
    assert fx["presets"]["nord"]["tokens"] == parse_theme("nord")
    for regime, entries in fx["random"].items():
        assert len(entries) >= 20 and len({json.dumps(e["seeds"]) for e in entries}) == len(entries)
        assert all(e["light"] == (regime == "light") for e in entries)
        assert all(list(e["tokens"]) == list(TOKENS) for e in entries)
        assert all(e["tokens"] == derive_theme(e["seeds"]) for e in entries)
    edges = [(e["seeds"]["bg"], e["seeds"]["fg"], e["light"]) for e in fx["edges"]]
    assert edges == [
        ("#808080", "#808080", False),
        ("#777777", "#787878", False),
        ("#787878", "#777777", True),
    ]


def test_themes_prints_tokens(capsys):
    assert cli.main(["themes", "--theme", "nord"]) == 0
    assert "  ACCENT_3     #5B7A88" in capsys.readouterr().out


# --- sheet ---------------------------------------------------------------------------------


def test_sheet_recolors_through_slots(wallpapers, tmp_path, capsys):
    piece(wallpapers, "tiny")
    piece(wallpapers, "flat", FLAT)
    versions(wallpapers)
    piece(wallpapers, "unbuilt")
    built(capsys, "tiny", "flat", "versions")
    out = tmp_path / "s.png"
    args = [
        "sheet",
        "tiny",
        "flat",
        "unbuilt",
        "--theme",
        "flexoki-light",
        "--cols",
        "1",
        "--thumb",
        "160",
        "-o",
        str(out),
    ]
    assert cli.main(args) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == str(out)
    assert captured.err == "skip unbuilt: not built (run walldye build unbuilt)\n"
    assert Image.open(out).size == (8 + 160 + 8, 2 * (90 + 8 + 22) + 8)
    args = [
        "sheet",
        "tiny",
        "versions",
        "--variant",
        "late",
        "--aspect",
        "10:16",
        "--thumb",
        "90",
        "-o",
        str(out),
    ]
    assert cli.main(args) == 0
    assert capsys.readouterr().err == "skip tiny: no variant late\n"
    assert Image.open(out).size == (8 + 90 + 8, 144 + 8 + 22 + 8)
    shutil.rmtree(common.build_dir("versions", "late"))
    with pytest.raises(SystemExit, match="nothing to put on a sheet"):
        cli.main([a for a in args if a != "tiny"])
    assert (
        capsys.readouterr().err
        == "skip versions: not built (run walldye build versions --variant late)\n"
    )


def test_themed_matches_a_render(wallpapers, capsys):
    piece(wallpapers, "tiny")
    built(capsys, "tiny")
    template = (common.build_dir("tiny") / "16x9.svg").read_text()
    assert sheet.themed("tiny", parse_seeds("1C1B1A-DAD8CE-CF6A4C")) == template
    light = parse_seeds("flexoki-light")
    assert sheet.themed("tiny", light) == common.render("tiny", "flexoki-light")
    with pytest.raises(KeyError):
        sheet.themed("tiny", parse_seeds("nord"), aspect="4:3")


def test_sheet_default_path(wallpapers, tmp_path, monkeypatch, capsys):
    piece(wallpapers, "flat", FLAT)
    built(capsys, "flat")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["sheet", "--all", "--thumb", "64"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "sheet-fireproof.png")
    with pytest.raises(SystemExit, match="nothing to put on a sheet"):
        sheet.run([], parse_seeds(None), 4, 64, None)


# --- drop ---------------------------------------------------------------------------------------


def test_drop(wallpapers, review_files, monkeypatch, capsys):
    piece(wallpapers, "a")
    piece(wallpapers, "b")
    review.save_state({"a": {"status": "rejected"}, "b": {"note": "hm"}})
    featured = review_files / "featured.yaml"
    featured.write_text("# first\n- b\n- 'a'  # lead\n- ab\n")
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert cli.main(["drop", "a"]) == 1
    assert (wallpapers / "a").is_dir() and not (wallpapers / "index.json").exists()
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert cli.main(["drop", "a"]) == 0
    assert not (wallpapers / "a").exists()
    assert review.load_state() == {"b": {"note": "hm"}} and (wallpapers / "index.json").exists()
    assert featured.read_text() == "# first\n- b\n- ab\n"
    assert "took a off featured.yaml" in capsys.readouterr().out

    def no_prompt(prompt):
        raise AssertionError("--yes must not prompt")

    monkeypatch.setattr("builtins.input", no_prompt)
    assert cli.main(["drop", "b", "--yes"]) == 0
    assert not (wallpapers / "b").exists() and review.load_state() == {}
    with pytest.raises(SystemExit) as e:
        cli.main(["drop", "b"])
    assert e.value.code == 2

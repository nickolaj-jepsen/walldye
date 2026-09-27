import datetime
import json
import queue
import re
import sys
import threading
import types
import urllib.error
import urllib.request

import pytest
from PIL import Image

import walldye
import walldye.tools
from walldye import _theme
from walldye.tools import cli, common, listing, new, preview, review, sheet
from walldye.tools import lint as real_lint

# Ring everywhere; the dot only in the light regime, so light geometry differs.
TINY = '''"""A ring with a dot that only the light regime draws."""

from walldye import ACCENT, UI, H, W, is_light

ASPECTS = ["any"]


def draw(s):
    s.circle(W / 2, H / 2, 200, fill="none", stroke=UI, stroke_width=2)
    if is_light():
        s.circle(W / 2, H / 2, 20, fill=ACCENT)
'''
FLAT = "from walldye import UI\n\n\ndef draw(s):\n    s.rect(10, 10, 100, 100, fill=UI)\n"


def piece(wallpapers, slug, design=TINY, **meta):
    d = wallpapers / slug
    d.mkdir()
    (d / "design.py").write_text(design)
    new.write_meta(slug, {"title": slug.capitalize(), "description": "A test piece.", "draft": True, **meta})
    return d


def built(wallpapers, slug, **meta):
    """A piece with build/16x9.svg (fireproof render) and a slots.json with an entry per regime it has."""
    d = piece(wallpapers, slug, **meta)
    (d / "build").mkdir()
    (d / "build/16x9.svg").write_text(common.render(slug, "fireproof"))
    regimes = meta.get("themes") or ["dark", "light"]
    slots = {f"16:9/{r}": {"file": "16x9.svg", "regime": r} for r in regimes}
    (d / "build/slots.json").write_text(json.dumps(slots))
    return d


def meta(slug):
    return common.load_meta(slug)


def module(monkeypatch, name, **attrs):
    """Install a stand-in for walldye.tools.<name> (owned by the build agent) for this test."""
    mod = types.ModuleType(f"walldye.tools.{name}")
    mod.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, mod.__name__, mod)
    monkeypatch.setattr(walldye.tools, name, mod, raising=False)
    return mod


@pytest.fixture
def fake_tokenize(monkeypatch):
    pat = re.compile(r'(?:fill|stroke)="(#[0-9A-Fa-f]{6})"')
    module(
        monkeypatch,
        "tokenize",
        find_colours=lambda svg: [(m.start(1), m.end(1), m.group(1).upper()) for m in pat.finditer(svg)],
        skeleton=lambda svg: pat.sub(lambda m: m.group(0).replace(m.group(1), "#"), svg),
    )


@pytest.fixture
def fake_lint(monkeypatch, fake_tokenize):
    """Stand-ins for walldye.tools.lint that report what they were handed."""
    module(
        monkeypatch,
        "lint",
        svg=lambda text: (["svg: <text>"] if "<text" in text else [], []),
        source=lambda path: ([], ["source: luminance"] if "luminance(" in path.read_text() else []),
        copy_words=real_lint.copy_words,
        pixel_origins=lambda grids: [f"origin {x:g},{y:g}" for _, x, y in grids if x % 1 or y % 1],
        license_of=lambda m: m.get("license") or ("CC0-1.0" if m.get("ai_generated") else None),
    )


@pytest.fixture
def fake_build(monkeypatch):
    calls = {"recolour": [], "write_index": 0, "run": []}

    def select(slots, aspect, seeds):
        light = _theme.is_light(seeds["bg"], seeds["fg"])
        if light and f"{aspect}/light" not in slots:
            return f"{aspect}/dark", {**seeds, "bg": seeds["fg"], "fg": seeds["bg"]}
        return f"{aspect}/{'light' if light else 'dark'}", seeds

    def recolour(template, entry, seeds):
        calls["recolour"].append((entry["regime"], seeds))
        return template.replace("</svg>", f"<!--{walldye.theme_token(seeds)}--></svg>")

    def write_index():
        calls["write_index"] += 1

    def run(slugs, all=False, verify=False, force=False):
        calls["run"].append((slugs, all, verify, force))
        return 0

    def load_slots(slug):
        return json.loads((common.build_dir(slug) / "slots.json").read_text())

    module(
        monkeypatch, "build", load_slots=load_slots, select=select, recolour=recolour, write_index=write_index, run=run
    )
    return calls


@pytest.fixture
def review_files(tmp_path, monkeypatch):
    files = tmp_path / "repo"
    files.mkdir()
    monkeypatch.setattr(review, "STATE_FILE", files / ".walldye-review.json")
    monkeypatch.setattr(common, "TAXONOMY", files / "taxonomy.yaml")
    return files


# --- new -----------------------------------------------------------------------


def test_new_scaffolds_a_draft(wallpapers, capsys):
    assert cli.main(["new", "ring-one", "--author", "Claude Opus 5.5", "--model", "claude-opus-5-5"]) == 0
    d = wallpapers / "ring-one"
    assert capsys.readouterr().out.strip() == str(d)
    text = (d / "meta.yaml").read_text()
    assert "license" not in text
    assert "technique: []\n" in text and "proposed_facets: {}\n" in text
    m = meta("ring-one")
    assert m["draft"] is True and m["ai_generated"] is True
    assert m["added"] == datetime.date.today()
    assert (m["author"], m["model"]) == ("Claude Opus 5.5", "claude-opus-5-5")
    assert "<circle" in common.render("ring-one", "nord")
    assert common.design_aspects("ring-one") == ["16:9"]


@pytest.mark.parametrize("slug", ["about", "sitemap-index", "og", "Bad_Slug", "-x", "taken"])
def test_new_refuses(wallpapers, slug):
    (wallpapers / "taken").mkdir()
    with pytest.raises(SystemExit) as e:
        new.run(slug, "a", "m")
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


def test_render_names_file_after_slug_token_and_aspect(wallpapers, tmp_path, monkeypatch, capsys):
    piece(wallpapers, "tiny")
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(out)
    assert cli.main(["render", "tiny", "--theme", "2E3440-ECEFF4-88C0D0", "--aspect", "21:9"]) == 0
    f = out / "tiny-nord-21x9.svg"
    assert capsys.readouterr().out.strip() == "tiny-nord-21x9.svg"
    assert f.read_text() == common.render("tiny", "nord", "21:9")
    assert 'viewBox="0 0 2520 1080"' in f.read_text()

    assert cli.main(["render", "tiny", "--theme", "1c1b1b-dad8ce-cf6a4c", "--crop", "100,50,400,300"]) == 0
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
    piece(wallpapers, "chatty", TINY.replace("def draw(s):", "def draw(s):\n    print('debug')"))
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
    with pytest.raises(SystemExit, match="declares ASPECTS"):
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
    ):
        with pytest.raises(SystemExit) as e:
            cli.main(bad)
        assert e.value.code == 2
    piece(wallpapers, "odd", FLAT + '\nASPECTS = ["banana"]\n')
    with pytest.raises(SystemExit, match=r"design.py: ASPECTS entry 'banana'"):
        cli.main(["render", "odd", "-o", str(tmp_path / "x.svg")])


# --- preview ----------------------------------------------------------------------


def test_preview_writes_png_and_reports(wallpapers, tmp_path, monkeypatch, capsys, fake_lint):
    piece(wallpapers, "tiny")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path / "prev"))
    assert cli.main(["preview", "tiny", "--theme", "flexoki-light", "--aspect", "9:19.5", "--width", "400"]) == 0
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


def test_preview_prints_lint_lines(wallpapers, tmp_path, monkeypatch, capsys, fake_lint):
    design = (
        "from walldye import UI, grid_runs, luminance\n\n\n"
        "def draw(s):\n    s.rect(0, 0, 10, 10, fill='#88C0D0')\n    s.rect(0, 0, 10, 10, fill='#FF00FF')\n"
        "    grid_runs(s, [[1]], [None, UI], 4, 0.5, 3)\n    s.text(1, 2, 'x')\n    return luminance(UI)\n"
    )
    piece(wallpapers, "loud", design, description="A crimson disc.")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "loud", "--theme", "nord", "--width", "64"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:4] == [
        "error: svg: <text>",
        "warning: source: luminance",
        "warning: colour words in meta.yaml copy: crimson (describe the shape or what it picks out, without naming colours)",
        "warning: origin 0.5,3",
    ]
    # Judged under nord, the render's theme: its hardcoded accent #88C0D0 is on the palette.
    assert re.fullmatch(
        r"hint: 1 colour\(s\) off the theme, hardcoded unless inside a mask: #FF00FF \(Δ\d+\)", lines[4]
    )
    assert lines[5] == "lint: 1 error(s), 3 warning(s)"


def test_preview_dark_only_and_undeclared_aspect(wallpapers, tmp_path, monkeypatch, capsys, fake_lint):
    piece(wallpapers, "flat", FLAT, themes=["dark"])
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "flat", "--aspect", "21:9", "--width", "200"]) == 0
    out = capsys.readouterr().out
    assert "warning: flat declares ASPECTS=['16:9']; rendered 21:9 anyway" in out
    assert "light geometry: n/a (themes: [dark])" in out


def test_preview_legacy_piece(wallpapers, tmp_path, monkeypatch, capsys, fake_lint):
    d = wallpapers / "old"
    d.mkdir()
    (d / "source.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">'
        '<rect x="0" y="0" width="1920" height="1080" fill="#1C1B1A"/>'
        '<circle cx="960" cy="540" r="90" fill="#CF6A4C"/></svg>\n'
    )
    (d / "palette.yaml").write_text('"#1C1B1A": bg\n"#CF6A4C": accent\n')
    new.write_meta("old", {"title": "Old", "description": "A disc.", "draft": True})
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "old", "--theme", "nord", "--width", "64"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:3] == [
        "lint: ok",
        "regime: dark (nord)",
        "light geometry: same as dark (one template serves both regimes)",
    ]


def test_lint_checks_the_viewbox(wallpapers, fake_lint):
    piece(wallpapers, "tiny")
    svg = common.render("tiny", "fireproof")
    assert preview.lint("tiny", svg, "16:9", []) == ([], [], [])
    assert preview.lint("tiny", svg, "21:9", [])[0] == ['viewBox is not "0 0 2520 1080"']
    assert preview.lint("tiny", '<?xml version="1.0"?>\n' + svg, "16:9", [])[0] == []


def test_crop_parsing():
    assert preview.parse_crop("1,2.5,3,4") == (1, 2.5, 3, 4)
    for bad in ("1,2,3", "1,2,0,4", "a,b,c,d", "1,2,3,-4"):
        with pytest.raises(ValueError):
            preview.parse_crop(bad)


# --- check / build wiring --------------------------------------------------------------


def test_check_and_build_wiring(wallpapers, monkeypatch, fake_build):
    piece(wallpapers, "tiny")
    runs = []
    module(monkeypatch, "check", run=lambda slugs, all=False, set_mode=False: runs.append((slugs, all, set_mode)) or 3)
    assert cli.main(["check", "tiny", "--set"]) == 3
    assert cli.main(["check", "--all"]) == 3
    assert runs == [(["tiny"], False, True), ([], True, False)]
    assert cli.main(["build", "--verify"]) == 0
    assert cli.main(["build", "tiny"]) == 0
    assert cli.main(["build", "--all", "--verify"]) == 0
    assert cli.main(["build", "tiny", "--force"]) == 0
    assert fake_build["run"] == [([], False, True, False), (["tiny"], False, False, False), ([], True, True, False), (["tiny"], False, False, True)]
    for bad in (["check"], ["check", "--all", "tiny"], ["build"], ["sheet"], ["check", "missing"], ["check", "Bad"]):
        with pytest.raises(SystemExit) as e:
            cli.main(bad)
        assert e.value.code == 2


def test_hashes_hands_off_to_check(monkeypatch):
    seen = []
    module(monkeypatch, "check", hashes_main=lambda args: seen.append(args) or 0)
    assert cli.main(["_hashes", "/w", "tiny@16:9@nord", "tiny@9:19.5@1c1b1b-dad8ce-cf6a4c"]) == 0
    assert seen == [["/w", "tiny@16:9@nord", "tiny@9:19.5@1c1b1b-dad8ce-cf6a4c"]]
    assert "_hashes" not in cli._parser().format_help()


# --- list / themes -----------------------------------------------------------------------


def test_list(wallpapers, capsys):
    piece(wallpapers, "tiny", title="Tiny\tring", description="A ring,\n  drawn once.")
    piece(wallpapers, "flat", FLAT, draft=False)
    assert cli.main(["list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "flat\tFlat\tA test piece.\t-\t16:9",
        f"tiny\tTiny ring\tA ring, drawn once.\tdraft\t{','.join(walldye.SITE_ASPECTS)}",
    ]


def test_themes_fixture(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(listing, "FIXTURE", tmp_path / "fx/themes.json")
    assert cli.main(["themes", "--json"]) == 0
    out = capsys.readouterr().out
    assert "fireproof          #1C1B1A #DAD8CE #CF6A4C  dark (default)" in out
    assert out.splitlines()[-1] == str(listing.FIXTURE)
    fx = json.loads(listing.FIXTURE.read_text())
    assert list(fx["presets"]) == list(walldye.PRESETS)
    assert fx["presets"]["fireproof"]["tokens"] == walldye.PRESETS["fireproof"]
    assert fx["presets"]["nord"]["tokens"] == walldye.parse_theme("nord")
    for regime, entries in fx["random"].items():
        assert len(entries) >= 20 and len({json.dumps(e["seeds"]) for e in entries}) == len(entries)
        assert all(e["light"] == (regime == "light") for e in entries)
        assert all(list(e["tokens"]) == list(walldye.TOKENS) for e in entries)
        assert all(e["tokens"] == walldye.derive_theme(e["seeds"]) for e in entries)
    edges = [(e["seeds"]["bg"], e["seeds"]["fg"], e["light"]) for e in fx["edges"]]
    assert edges == [("#808080", "#808080", False), ("#777777", "#787878", False), ("#787878", "#777777", True)]
    assert cli.main(["themes", "--json"]) == 0
    assert json.loads(listing.FIXTURE.read_text()) == fx


def test_committed_themes_fixture_is_current():
    assert json.loads(listing.FIXTURE.read_text()) == listing.fixture(), "run uv run walldye themes --json"


def test_themes_prints_tokens(capsys):
    assert cli.main(["themes", "--theme", "nord"]) == 0
    assert "  ACCENT_3     #5B7A88" in capsys.readouterr().out


# --- sheet ---------------------------------------------------------------------------------


def test_sheet_recolours_through_slots(wallpapers, tmp_path, capsys, fake_build):
    built(wallpapers, "a")
    built(wallpapers, "b", themes=["dark"])
    piece(wallpapers, "unbuilt")
    (built(wallpapers, "half") / "build/slots.json").unlink()
    out = tmp_path / "s.png"
    args = ["sheet", "a", "b", "unbuilt", "half", "--theme", "flexoki-light", "--cols", "1", "--thumb", "160", "-o", str(out)]
    assert cli.main(args) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == str(out)
    assert "skip unbuilt: not built (run walldye build unbuilt)" in captured.err
    assert "skip half: not built (run walldye build half)" in captured.err
    assert Image.open(out).size == (8 + 160 + 8, 2 * (90 + 8 + 22) + 8)
    light = walldye.parse_seeds("flexoki-light")
    swapped = {**light, "bg": light["fg"], "fg": light["bg"]}
    assert fake_build["recolour"] == [("light", light), ("dark", swapped)]


def test_themed_leaves_fireproof_untouched(wallpapers, fake_build):
    d = built(wallpapers, "a")
    assert sheet.themed("a", walldye.parse_seeds("1C1B1A-DAD8CE-CF6A4C")) == (d / "build/16x9.svg").read_text()
    assert sheet.themed("a", walldye.parse_seeds("nord")).endswith("<!--nord--></svg>\n")
    assert fake_build["recolour"] == [("dark", walldye.parse_seeds("nord"))]


def test_sheet_default_path(wallpapers, tmp_path, monkeypatch, capsys, fake_build):
    built(wallpapers, "a")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["sheet", "--all", "--thumb", "64"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "sheet-fireproof.png")
    with pytest.raises(SystemExit, match="nothing to put on a sheet"):
        sheet.run([], walldye.parse_seeds(None), 4, 64, None)


# --- review ------------------------------------------------------------------------------------


def test_apply_publishes_and_settles_facets(wallpapers, review_files, fake_build):
    built(wallpapers, "a", technique=["drafting"])
    built(wallpapers, "b", proposed_facets={"technique": ["weave", "stipple"], "subject": ["moon"]})
    built(wallpapers, "c", proposed_facets={"subject": ["sea"]})
    built(wallpapers, "d")
    common.TAXONOMY.write_text(
        "# Facet vocabulary.\n# Only review adds values.\ntechnique:\n  - drafting\nsubject: []\n"
    )
    state = {
        "a": {"status": "approved"},
        "b": {
            "status": "approved",
            "facets": {"technique": {"weave": "accept", "stipple": "decline"}, "subject": {"moon": "accept"}},
        },
        "c": {"status": "approved", "facets": {"subject": {}}},
        "d": {"status": "rejected", "note": "too busy"},
    }
    result = review.apply(["a", "b", "c", "d"], state)
    assert result == {
        "published": ["a", "b"],
        "refused": [{"slug": "c", "reason": "proposed facets undecided: subject: sea"}],
    }
    assert meta("a")["draft"] is False and meta("a")["technique"] == ["drafting"]
    b = meta("b")
    assert b["draft"] is False and "proposed_facets" not in b
    assert (b["technique"], b["subject"]) == (["weave"], ["moon"])
    assert meta("c")["draft"] is True and meta("c")["proposed_facets"] == {"subject": ["sea"]}
    assert meta("d")["draft"] is True
    assert common.TAXONOMY.read_text() == (
        "# Facet vocabulary.\n# Only review adds values.\ntechnique:\n  - drafting\n  - weave\nsubject:\n  - moon\n"
    )
    assert fake_build["write_index"] == 1


def test_apply_without_approvals_writes_nothing(wallpapers, review_files, fake_build):
    built(wallpapers, "a")
    before = (wallpapers / "a/meta.yaml").read_text()
    assert review.apply(["a"], {"a": {"status": "rejected"}}) == {"published": [], "refused": []}
    assert (wallpapers / "a/meta.yaml").read_text() == before
    assert not common.TAXONOMY.exists() and fake_build["write_index"] == 0


def serve(monkeypatch, capsys, slugs, timeout=30):
    """Run review.run in a thread; returns (base url, finish() -> printed JSON)."""
    urls = queue.Queue()
    monkeypatch.setattr(review.webbrowser, "open", urls.put)
    codes = []
    t = threading.Thread(target=lambda: codes.append(review.run(slugs, timeout, 0, True)))
    t.start()
    url = urls.get(timeout=10)

    def finish(code=0):
        t.join(timeout=10)
        assert codes == [code]
        out = capsys.readouterr().out
        return json.loads(out[out.index("{") :])

    return url, finish


def http(url, data=None):
    body = None if data is None else json.dumps(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body, method="POST" if body else "GET")) as r:
        return r.read()


def test_review_round_trip(wallpapers, review_files, monkeypatch, capsys, fake_build, fake_lint):
    built(wallpapers, "a", sources=[{"kind": "inspiration", "title": "</script><b>x", "author": "Someone"}])
    d = built(wallpapers, "b", proposed_facets={"subject": ["moon"]}, ai_generated=True)
    (d / "build/16x9.light.svg").write_text("<svg>light</svg>")
    (d / "build/21x9.svg").write_text("<svg>wide</svg>")
    built(wallpapers, "published", draft=False)
    review.save_state({"other": {"status": "rejected"}})

    url, finish = serve(monkeypatch, capsys, [])  # defaults to the drafts: a, b
    page = http(url).decode()
    cfg = json.loads(re.search(r"const CFG = (.*);\n", page).group(1))
    assert [c["slug"] for c in cfg["cards"]] == ["a", "b"]
    a, b = cfg["cards"]
    assert "</script><b>" not in page and a["sources"][0]["title"] == "</script><b>x"
    assert (a["license"], b["license"], a["light"], b["light"]) == (
        "missing (walldye check says why)",
        "CC0-1.0 (default)",
        "light/a.svg",
        "svg/b/16x9.light.svg",
    )
    assert b["strip"] == [{"aspect": "21:9", "src": "svg/b/21x9.svg"}] and b["proposed"] == {"subject": ["moon"]}
    assert http(url + "svg/b/21x9.svg") == b"<svg>wide</svg>"
    assert http(url + "light/a.svg").decode().endswith("<!--flexoki-light--></svg>\n")
    for missing in ("svg/published/16x9.svg", "svg/a/slots.json", "svg/a/..%2Fmeta.yaml", "light/b.svg.bak", "nope"):
        with pytest.raises(urllib.error.HTTPError):
            http(url + missing)

    state = {"a": {"status": "approved", "note": "keep"}, "b": {"status": "approved"}}
    assert http(url + "state", state) == b"ok"
    assert review.load_state() == {**state, "other": {"status": "rejected"}}
    done = json.loads(http(url + "done", {}))
    printed = finish()
    assert printed == done
    assert printed == {
        "approved": ["a", "b"],
        "rejected": [],
        "undecided": [],
        "notes": {"a": "keep"},
        "published": ["a"],
        "refused": [{"slug": "b", "reason": "proposed facets undecided: subject: moon"}],
        "finished": True,
    }
    assert meta("a")["draft"] is False and meta("b")["draft"] is True
    assert fake_build["write_index"] == 1


def test_review_reports_a_failed_apply(wallpapers, review_files, monkeypatch, capsys, fake_build):
    built(wallpapers, "a", proposed_facets={"technique": ["weave"]})
    common.TAXONOMY.write_text("technique: {drafting: a mapping, not a list}\n")
    review.save_state({"a": {"status": "approved", "facets": {"technique": {"weave": "accept"}}}})
    url, finish = serve(monkeypatch, capsys, ["a"])
    with pytest.raises(urllib.error.HTTPError) as e:
        http(url + "done", {})
    assert e.value.code == 500
    sent = json.loads(e.value.read())
    printed = finish(code=1)
    assert printed == sent
    assert printed["finished"] is False and printed["published"] == [] and printed["approved"] == ["a"]
    assert printed["error"] == f"ValueError: {common.TAXONOMY}: technique must be a list of values"
    assert meta("a")["draft"] is True and fake_build["write_index"] == 0


def test_review_timeout_applies_nothing(wallpapers, review_files, monkeypatch, capsys, fake_build):
    built(wallpapers, "a")
    review.save_state({"a": {"status": "approved"}})
    _, finish = serve(monkeypatch, capsys, ["a"], timeout=0.2)
    out = finish()
    assert out["finished"] is False and out["approved"] == ["a"] and out["published"] == []
    assert meta("a")["draft"] is True and fake_build["write_index"] == 0


def test_review_refuses_unbuilt_and_empty(wallpapers, review_files):
    built(wallpapers, "a")
    piece(wallpapers, "raw")
    with pytest.raises(SystemExit, match=r"not built: raw \(run walldye build raw\)"):
        review.run(["a", "raw"], 1, 0, False)
    (wallpapers / "raw/meta.yaml").unlink()
    new.write_meta("a", {**meta("a"), "draft": False})
    with pytest.raises(SystemExit, match="no drafts"):
        review.run([], 1, 0, False)


# --- drop ---------------------------------------------------------------------------------------


def test_drop(wallpapers, review_files, monkeypatch, capsys, fake_build):
    piece(wallpapers, "a")
    piece(wallpapers, "b")
    review.save_state({"a": {"status": "rejected"}, "b": {"note": "hm"}})
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert cli.main(["drop", "a"]) == 1
    assert (wallpapers / "a").is_dir() and fake_build["write_index"] == 0
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert cli.main(["drop", "a"]) == 0
    assert not (wallpapers / "a").exists()
    assert review.load_state() == {"b": {"note": "hm"}} and fake_build["write_index"] == 1

    def no_prompt(prompt):
        raise AssertionError("--yes must not prompt")

    monkeypatch.setattr("builtins.input", no_prompt)
    assert cli.main(["drop", "b", "--yes"]) == 0
    assert not (wallpapers / "b").exists() and review.load_state() == {}
    with pytest.raises(SystemExit) as e:
        cli.main(["drop", "b"])
    assert e.value.code == 2

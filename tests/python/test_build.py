import importlib.metadata
import json
import random

import numpy as np
import pytest
from fixtures import regen

import walldye
from walldye import _basis
from walldye._theme import SEEDS
from walldye.tools import build, check, common, fit, hashing, lint, listing, review
from walldye.tools.tokenize import find_colours, normalise, skeleton

FIREPROOF = {k: walldye.PRESETS["fireproof"][k] for k in SEEDS}
ALL_HELD_OUT = _basis.HELD_OUT["dark"] + _basis.HELD_OUT["light"]


def built(capsys, *slugs, **kw) -> str:
    code = build.run(list(slugs), **kw)
    out = capsys.readouterr().out
    assert code == 0, out
    return out


def seeds(theme) -> dict[str, str]:
    return walldye.parse_seeds(theme) if isinstance(theme, str) else dict(zip(SEEDS, theme))


def assert_recolours(slug: str, theme, aspect: str = "16:9") -> None:
    """build.recolour of the committed template matches a fresh render: same skeleton, slots within 2."""
    slots = build.load_slots(slug)
    key, applied = build.select(slots, aspect, seeds(theme))
    template = (common.build_dir(slug) / slots[key]["file"]).read_text()
    got = build.recolour(template, slots[key], applied)
    want = common.render(slug, applied, aspect)
    assert skeleton(got) == skeleton(want)
    assert np.abs(fit.colours(got) - fit.colours(want)).max(initial=0) <= fit.MAX_ERROR


# --- build output -----------------------------------------------------------------


def test_collision_builds_and_recolours(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    assert "collision: wrote 16x9.svg, slots.json" in built(capsys, "collision")
    b = common.build_dir("collision")
    assert sorted(p.name for p in b.iterdir()) == ["16x9.svg", "slots.json"]
    template = (b / "16x9.svg").read_text()
    assert template == normalise(common.render("collision", "fireproof"))

    slots = build.load_slots("collision")
    assert list(slots) == [
        "design_sha",
        "focus",
        "cells",
        "probes",
        "checked",
        "16:9/dark",
        "16:9/light",
    ]
    assert slots["design_sha"] == hashing.design_sha("collision")
    assert slots["checked"] == build.version()
    assert slots["cells"] == [] and len(slots["focus"]) == 2
    assert set(slots["probes"]) == {"fireproof", "dark", "light"}
    assert slots["probes"]["fireproof"] == hashing.sha256(
        common.render("collision", "fireproof").encode()
    )
    for regime in ("dark", "light"):
        entry = slots[f"16:9/{regime}"]
        assert list(entry) == ["file", "sha256", "n", "coefs", "occ"]
        assert entry["file"] == "16x9.svg" and entry["sha256"] == hashing.sha256(template.encode())
        assert entry["n"] == len(entry["occ"]) == len(find_colours(template)) == 3
        assert all(len(row) == 6 for row in entry["coefs"]) and max(entry["occ"]) < len(
            entry["coefs"]
        )

    for theme in regen.RECOLOUR_THEMES + ALL_HELD_OUT:
        assert_recolours("collision", theme)
    assert build.recolour(template, slots["16:9/dark"], FIREPROOF) == template
    assert build.recolour(template, {**slots["16:9/dark"], "n": 2}, seeds("nord")) == template


def test_recolour_evaluates_like_predict():
    r = random.Random(1)
    rows = [
        [round(r.uniform(-1, 1.5), 5) for _ in range(3)]
        + [round(r.uniform(-60, 60), 5) for _ in range(3)]
        for _ in range(40)
    ]
    template = "".join(f'<rect fill="#{i:06X}"/>' for i in range(40))
    for _ in range(20):
        theme = tuple(f"#{r.getrandbits(24):06X}" for _ in range(3))
        got = build.recolour(
            template, {"n": 40, "coefs": rows, "occ": list(range(40))}, dict(zip(SEEDS, theme))
        )
        assert (fit.colours(got) == fit.predict(np.array(rows), theme)).all()


def test_select():
    both = {"16:9/dark": {}, "16:9/light": {}}
    assert build.select(both, "16:9", seeds("nord")) == ("16:9/dark", seeds("nord"))
    assert build.select(both, "16:9", seeds("flexoki-light")) == (
        "16:9/light",
        seeds("flexoki-light"),
    )
    light = seeds("flexoki-light")
    swapped = {"bg": light["fg"], "fg": light["bg"], "accent": light["accent"]}
    assert build.select({"16:9/dark": {}}, "16:9", light) == ("16:9/dark", swapped)
    with pytest.raises(KeyError):
        build.select(both, "21:9", light)


def test_light_branch_gets_its_own_template(wallpapers, capsys):
    regen.install(wallpapers, "light-branch")
    built(capsys, "light-branch")
    slots = build.load_slots("light-branch")
    assert slots["16:9/dark"]["file"] == "16x9.svg"
    assert slots["16:9/light"]["file"] == "16x9.light.svg"
    light = (common.build_dir("light-branch") / "16x9.light.svg").read_text()
    assert light == normalise(common.render("light-branch", "flexoki-light"))
    assert '<rect x="860"' in light and "<circle" not in light
    for theme in ["solarized-light", "nord", *ALL_HELD_OUT]:
        assert_recolours("light-branch", theme)


def test_dark_only_piece_recolours_light_seeds_swapped(wallpapers, capsys):
    regen.install(
        wallpapers,
        "light-branch",
        "dark-only",
        themes=["dark"],
        notes="The square reads wrong on paper.",
    )
    regen.install(wallpapers, "light-branch", "both")
    assert hashing.design_sha("dark-only") != hashing.design_sha("both")
    built(capsys, "dark-only")
    slots = build.load_slots("dark-only")
    assert [k for k in slots if "/" in k] == ["16:9/dark"]
    assert set(slots["probes"]) == {"fireproof", "dark"}
    assert sorted(p.name for p in common.build_dir("dark-only").iterdir()) == [
        "16x9.svg",
        "slots.json",
    ]
    for theme in ["flexoki-light", "solarized-light", *_basis.HELD_OUT["light"]]:
        assert_recolours("dark-only", theme)


def test_any_aspect_pixel_design(wallpapers, capsys):
    regen.install(wallpapers, "pixels")
    out = built(capsys, "pixels")
    assert "pixel grid origin" in out
    b = common.build_dir("pixels")
    names = [walldye.template_name(a) for a in walldye.SITE_ASPECTS]
    assert sorted(p.name for p in b.glob("*.svg")) == sorted(names)
    slots = build.load_slots("pixels")
    assert slots["cells"] == [3]
    for aspect in walldye.SITE_ASPECTS:
        w, h = walldye.canvas_size(aspect)
        assert f'viewBox="0 0 {w} {h}"' in (b / walldye.template_name(aspect)).read_text()
        assert (
            slots[f"{aspect}/dark"]["file"]
            == slots[f"{aspect}/light"]["file"]
            == walldye.template_name(aspect)
        )
        assert_recolours("pixels", "nord", aspect)
    assert (
        json.loads((wallpapers / "index.json").read_text())["pixels"]["aspects"]
        == walldye.SITE_ASPECTS
    )


def test_legacy_piece(wallpapers, capsys):
    d = wallpapers / "old"
    d.mkdir()
    source = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">\n'
        '<rect x="0" y="0" width="1920" height="1080" fill="#1c1b1a"/>\n<circle cx="960" cy="540" r="200" fill="#CF6A4C"/>\n'
        '<path d="M0 0L100 100" stroke="#201A18"/>\n</svg>\n'
    )
    (d / "source.svg").write_text(source)
    (d / "palette.yaml").write_text(
        '"#1C1B1A": bg\n"#CF6A4C": accent\n"#201A18": [bg_deep, accent_8, 0.68]\n'
    )
    (d / "meta.yaml").write_text("title: Old\ndescription: A disc.\nai_generated: true\n")
    built(capsys, "old")
    assert (common.build_dir("old") / "16x9.svg").read_text() == source.replace(
        "#1c1b1a", "#1C1B1A"
    )
    for theme in ["nord", "flexoki-light", *ALL_HELD_OUT]:
        assert_recolours("old", theme)
    (d / "source.svg").write_text(source.replace('stroke="#201A18"', 'stroke="#123456"'))
    assert "hardcoded #123456" in " ".join(check.check_slug("old").errors)


def test_legacy_palette_maps_slots_not_hex_strings(wallpapers):
    d = wallpapers / "old"
    d.mkdir()
    (d / "source.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1920 1080">'
        '<defs><circle id="c0ffee" r="5" fill="#fff"/></defs><use xlink:href="#c0ffee"/>'
        '<use href="#c0ffee" stroke="white"/><rect fill="url(#c0ffee)" stroke="#C0FFEE"/></svg>'
    )
    (d / "palette.yaml").write_text('"#FFF": fg\n"#C0FFEE": accent\n')
    (d / "meta.yaml").write_text("title: Old\n")
    t = walldye.parse_theme("nord")
    assert common.render("old", "nord") == (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1920 1080">'
        f'<defs><circle id="c0ffee" r="5" fill="{t["fg"]}"/></defs><use xlink:href="#c0ffee"/>'
        f'<use href="#c0ffee" stroke="{t["fg"]}"/><rect fill="url(#c0ffee)" stroke="{t["accent"]}"/></svg>'
    )


def test_design_prints_go_to_stderr(wallpapers, capsys):
    regen.install(wallpapers, "collision", "chatty")
    design = wallpapers / "chatty/design.py"
    design.write_text(
        design.read_text().replace("def draw(s):", "def draw(s):\n    print('debug')")
    )
    assert check.check_slug("chatty").errors == []
    captured = capsys.readouterr()
    assert captured.out == "" and "debug" in captured.err


@pytest.mark.parametrize(
    ("aspects", "error"),
    [
        (
            "SITE_ASPECTS",
            'ASPECTS must be a literal list of strings, like ["any"] or ["16:9", "21:9"]',
        ),
        ('["banana"]', "ASPECTS entry 'banana' is not \"any\" or an aspect like 16:9"),
        ('["16:0"]', "ASPECTS entry '16:0' is not \"any\" or an aspect like 16:9"),
    ],
)
def test_bad_aspects_name_design_py(wallpapers, aspects, error):
    regen.install(wallpapers, "collision")
    design = wallpapers / "collision/design.py"
    design.write_text(design.read_text() + f"\nASPECTS = {aspects}\n")
    assert check.check_slug("collision").errors == [f"{design}: {error}"]


def test_meta_yaml_must_be_a_mapping(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    meta = wallpapers / "collision/meta.yaml"
    meta.write_text("- a\n- b\n")
    assert check.check_slug("collision").errors == [f"{meta}: must be a mapping"]
    assert build.run(["collision"]) == 1
    assert f"collision: {meta}: must be a mapping" in capsys.readouterr().out
    meta.write_text("title: [x\n")
    assert check.check_slug("collision").errors == [
        f"{meta}: not valid YAML (line 2): expected ',' or ']', but got '<stream end>'"
    ]


def test_design_exception_is_reported(wallpapers):
    regen.install(wallpapers, "collision")
    design = wallpapers / "collision" / "design.py"
    design.write_text(design.read_text() + "\n\ndef draw(s):\n    raise KeyError('nope')\n")
    assert check.check_slug("collision").errors == [
        "16:9: render under d82c07-629f6f-c2094c failed: KeyError: 'nope' (design.py line 13)"
    ]


# --- check failures -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("design", "expected"),
    [
        ("mask", None),
        ("masked-theme", "theme-dependent #"),
        ("hardcoded", "hardcoded #FF0000"),
        ("keyed", "geometry changes with the theme: probe 808080-808080-808080"),
        ("nonlinear", "16:9 dark: 16 of 16 held-out themes miss by more than 2 units"),
        ("forbidden", "<text>"),
        ("forbidden", "<filter>"),
        ("unseeded", "two renders under"),
        ("hash-order", "differs in a fresh process with PYTHONHASHSEED=4242"),
    ],
)
def test_check_catches(wallpapers, design, expected):
    regen.install(wallpapers, design)
    report = check.check_slug(design)
    if expected is None:
        assert report.errors == []
    else:
        assert any(expected in e for e in report.errors), report.errors


def test_determinism_failure_stops_before_geometry(wallpapers):
    regen.install(wallpapers, "unseeded")
    report = check.check_slug("unseeded")
    assert report.errors and all("two renders" in e for e in report.errors)
    assert report.templates == {} and report.entries == {}


def test_build_refuses_an_ill_conditioned_basis(wallpapers, capsys, monkeypatch):
    regen.install(wallpapers, "collision")
    monkeypatch.setitem(_basis.BASIS, "light", [("#000000", "#000000", "#000000")] * 8)
    assert build.run(["collision"]) == 1
    assert "the light basis has condition number" in capsys.readouterr().err
    assert not common.build_dir("collision").exists()


def test_failed_check_writes_nothing(wallpapers, capsys):
    regen.install(wallpapers, "hardcoded")
    assert build.run(["hardcoded"]) == 1
    assert "hardcoded: not written" in capsys.readouterr().out
    assert not common.build_dir("hardcoded").exists()
    assert not hashing.render_lib_stamp().exists()


def test_check_run_codes(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    assert check.run(["collision"]) == 0
    assert check.run([]) == 2
    assert check.run(["missing"]) == 1
    assert "missing: 1 error(s)" in capsys.readouterr().out


# --- staleness, restamp, verify ------------------------------------------------------


def test_skip_restamp_and_rebuild(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    built(capsys, "collision")
    stamp = hashing.render_lib_stamp()
    assert stamp.read_text() == hashing.render_lib_sha() + "\n"
    assert "collision: up to date" in built(capsys, "collision")

    stamp.write_text("0" * 64 + "\n")
    assert "probe renders unchanged" in built(capsys, "collision")
    assert stamp.read_text() == hashing.render_lib_sha() + "\n"

    slots = build.load_slots("collision")
    (common.build_dir("collision") / "slots.json").write_text(
        build.dump_slots({**slots, "probes": {**slots["probes"], "dark": "0"}})
    )
    stamp.write_text("0" * 64 + "\n")
    assert "collision: wrote" in built(capsys, "collision")

    design = common.piece_dir("collision") / "design.py"
    design.write_text(design.read_text() + "\n# edited\n")
    assert "collision: wrote" in built(capsys, "collision")
    assert "collision: wrote" in built(capsys, "collision", force=True)

    template = common.build_dir("collision") / "16x9.svg"
    template.write_text(template.read_text() + "<!-- hand edit -->\n")
    assert "collision: wrote" in built(capsys, "collision")
    slots = build.load_slots("collision")
    (common.build_dir("collision") / "slots.json").write_text(
        build.dump_slots({**slots, "checked": "0.0.0"})
    )
    assert "collision: wrote" in built(capsys, "collision")
    assert "collision: up to date" in built(capsys, "collision")


def test_build_applies_meta_rules_to_current_pieces(wallpapers, capsys):
    regen.install(
        wallpapers, "collision", sources=[{"kind": "recreation", "title": "X"}], license="CC0-1.0"
    )
    built(capsys, "collision")
    meta = wallpapers / "collision/meta.yaml"
    meta.write_text(meta.read_text().replace("license: CC0-1.0\n", ""))
    assert build.run(["collision"]) == 1
    out = capsys.readouterr().out
    assert "recreation source needs an explicit license" in out and "collision: not written" in out


def test_unreadable_slots_json_is_rebuilt(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    built(capsys, "collision")
    slots = common.build_dir("collision") / "slots.json"
    slots.write_text("{x")
    out = built(capsys, "collision")
    assert f"collision: {slots}: not valid JSON" in out and "collision: wrote" in out
    slots.write_text("[]")
    assert "collision: wrote" in built(capsys, "collision", force=True)


def test_probe_failure_is_reported_and_the_run_goes_on(wallpapers, capsys, monkeypatch):
    regen.install(wallpapers, "collision")
    regen.install(wallpapers, "collision", "other")
    built(capsys, all=True)
    hashing.render_lib_stamp().write_text("0" * 64 + "\n")
    real = common.render

    def render(slug, *args):
        if slug == "collision":
            raise RuntimeError("lib broke")
        return real(slug, *args)

    monkeypatch.setattr(common, "render", render)
    assert build.run([], all=True) == 1
    out = capsys.readouterr().out
    assert "failed: RuntimeError: lib broke" in out and "collision: not written" in out
    assert "other: up to date (probe renders unchanged" in out
    assert "run `walldye build --all` to restamp" in out


def test_unreadable_siblings_are_left_out(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    regen.install(wallpapers, "collision", "syntax")
    (wallpapers / "syntax/design.py").write_text("def draw(s)\n    pass\n")
    regen.install(wallpapers, "collision", "bad-yaml")
    (wallpapers / "bad-yaml/meta.yaml").write_text("title: [x\n")
    (wallpapers / "no-design").mkdir()
    (wallpapers / "no-design/meta.yaml").write_text("title: X\n")
    assert build.run(["collision"]) == 0
    captured = capsys.readouterr()
    assert "collision: wrote" in captured.out
    assert list(json.loads((wallpapers / "index.json").read_text())) == ["collision"]
    assert [line.split(":")[0] for line in captured.err.splitlines()] == ["index.json"] * 3

    assert listing.run_list() == 0
    captured = capsys.readouterr()
    assert [line.split("\t")[::4] for line in captured.out.splitlines()] == [
        ["collision", "16:9"],
        ["no-design", "error"],
        ["syntax", "error"],
    ]
    assert captured.err.startswith("list: left out bad-yaml: ")
    assert review.drafts() == ["collision", "syntax"]
    assert capsys.readouterr().err.startswith("review: skipped bad-yaml: ")


def test_partial_build_does_not_restamp(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    regen.install(wallpapers, "mask")
    out = built(capsys, "collision")
    assert "run `walldye build --all` to restamp" in out
    assert not hashing.render_lib_stamp().exists()
    built(capsys, all=True)
    assert hashing.render_lib_stamp().exists()


def test_verify(wallpapers, capsys):
    regen.install(wallpapers, "light-branch")
    regen.install(wallpapers, "mask")
    built(capsys, "light-branch")
    assert build.run(["light-branch"], verify=True) == 0
    assert "light-branch: ok" in capsys.readouterr().out
    light = common.build_dir("light-branch") / "16x9.light.svg"
    light.write_text(light.read_text().replace('x="860"', 'x="861"'))
    assert build.run([], verify=True) == 1
    out = capsys.readouterr().out
    assert "16x9.light.svg differs from a fresh render under flexoki-light, line 3" in out
    assert "mask: not built" in out
    assert not (common.build_dir("mask")).exists()


# --- index, hashes, lints -----------------------------------------------------------


def test_write_index(wallpapers):
    regen.install(wallpapers, "collision", "plain")
    regen.install(
        wallpapers,
        "collision",
        "recreation",
        draft=False,
        sources=[{"kind": "recreation", "title": "X"}],
    )
    regen.install(wallpapers, "pixels", "explicit", ai_generated=False, license="CC-BY-4.0")
    build.write_index()
    index = json.loads((wallpapers / "index.json").read_text())
    assert index == {
        "explicit": {
            "aspects": walldye.SITE_ASPECTS,
            "draft": True,
            "license": "CC-BY-4.0",
            "title": "Fixture",
        },
        "plain": {"aspects": ["16:9"], "draft": True, "license": "CC0-1.0", "title": "Fixture"},
        "recreation": {"aspects": ["16:9"], "draft": False, "license": None, "title": "Fixture"},
    }


def test_design_sha_lines(wallpapers):
    regen.install(wallpapers, "collision")
    design = (wallpapers / "collision" / "design.py").read_bytes()
    assert hashing.design_lines("collision") == [
        f"wallpapers/collision/design.py\t{hashing.sha256(design)}",
        "themes\tdark,light",
    ]
    legacy = wallpapers / "old"
    legacy.mkdir()
    (legacy / "source.svg").write_text("<svg/>")
    (legacy / "palette.yaml").write_text("{}\n")
    (legacy / "meta.yaml").write_text("themes: [dark]\n")
    assert [line.split("\t")[0] for line in hashing.design_lines("old")] == [
        "wallpapers/old/source.svg",
        "wallpapers/old/palette.yaml",
        "themes",
    ]
    assert hashing.design_lines("old")[-1] == "themes\tdark"


def test_committed_wallpapers_are_current():
    """CI's hash steps, in Python: every committed piece and the render-lib stamp match their inputs."""
    for slug in common.slugs():
        assert build._current(slug, build.load_slots(slug), hashing.design_sha(slug)), (
            f"{slug} is stale: run uv run walldye build {slug}"
        )
    assert hashing.stamped_render_lib_sha() == hashing.render_lib_sha(), (
        "render inputs changed: run uv run walldye build --all"
    )


def test_render_lib_lines():
    lines = hashing.render_lib_lines()
    keys = [line.split("\t")[0] for line in lines]
    assert "walldye/__init__.py" in keys and "walldye/_basis.py" in keys
    assert not any(k.startswith("walldye/tools/") or "__pycache__" in k for k in keys)
    assert [line for line in lines if line.startswith("dep\t")] == [
        f"dep\t{name}=={importlib.metadata.version(name)}"
        for name in ("numpy", "scikit-image", "scipy", "shapely")
    ]
    assert f"python\t{(common.ROOT / '.python-version').read_text().strip()}" in lines


def test_hash_vector():
    vector = json.loads((regen.SHARED / "hash-vector.json").read_text())
    lines = [
        *(f"{p}\t{hashing.sha256(t.encode())}" for p, t in vector["files"].items()),
        *vector["lines"],
    ]
    assert hashing.digest(lines) == vector["sha256"]
    assert hashing.sha256(vector["text"].encode()) == vector["sha256"]


def test_shared_fixtures_are_current():
    for rel, text in regen.outputs().items():
        path = regen.SHARED / rel
        assert path.exists() and path.read_text() == text, (
            f"{path} is stale: run uv run python tests/python/fixtures/regen.py"
        )


REFERENCE_MANIFEST = json.loads((regen.REFERENCE / "manifest.json").read_text())


def test_reference_renders_are_current():
    stale = "tests/fixtures/ is stale: run uv run python tests/python/fixtures/regen.py"
    assert REFERENCE_MANIFEST["themes"] == regen.RECOLOUR_THEMES, stale
    want = []
    for slug in regen.REFERENCE_PIECES:
        slots = build.load_slots(slug)
        assert REFERENCE_MANIFEST["pieces"][slug]["design_sha"] == slots["design_sha"], stale
        aspects = dict.fromkeys(
            k.split("/")[0] for k, v in slots.items() if isinstance(v, dict) and "file" in v
        )
        want += [(slug, a, t) for a in aspects for t in regen.RECOLOUR_THEMES]
    assert [(r["slug"], r["aspect"], r["theme"]) for r in REFERENCE_MANIFEST["renders"]] == want, (
        stale
    )
    for r in REFERENCE_MANIFEST["renders"]:
        assert build.load_slots(r["slug"])[r["entry"]]["sha256"] == r["sha256"], stale
        assert (common.ROOT / r["render"]).exists(), stale


@pytest.mark.parametrize(
    "ref", REFERENCE_MANIFEST["renders"], ids=lambda r: r["render"].removeprefix("tests/fixtures/")
)
def test_reference_renders_recolour(ref):
    """vitest (b) on the Python side: recolouring the committed template matches the reference render."""
    slots = build.load_slots(ref["slug"])
    key, applied = build.select(slots, ref["aspect"], seeds(ref["theme"]))
    assert key == ref["entry"]
    got = build.recolour((common.ROOT / ref["template"]).read_text(), slots[key], applied)
    want = (common.ROOT / ref["render"]).read_text()
    assert skeleton(got) == skeleton(want)
    assert np.abs(fit.colours(got) - fit.colours(want)).max(initial=0) <= fit.MAX_ERROR


TAXONOMY = {"technique": {"drafting", "dither"}, "subject": {"space"}}
GOOD = {"title": "T", "description": "A disc.", "ai_generated": True, "technique": ["dither"]}


@pytest.mark.parametrize(
    ("slug", "meta", "error"),
    [
        ("ok", GOOD, None),
        ("ok", {**GOOD, "title": ""}, "needs a title"),
        ("about", GOOD, "reserved"),
        ("sitemap-x", GOOD, "reserved"),
        ("ok", {**GOOD, "themes": ["light"]}, "themes must be"),
        ("ok", {**GOOD, "themes": ["dark"], "notes": "why"}, None),
        (
            "ok",
            {**GOOD, "sources": [{"kind": "recreation"}]},
            "recreation source needs an explicit license",
        ),
        ("ok", {**GOOD, "sources": [{"kind": "recreation"}], "license": "CC0-1.0"}, None),
        ("ok", {**GOOD, "sources": [{"kind": "homage"}]}, "source kind"),
        ("ok", {**GOOD, "ai_generated": False}, "human-made"),
        ("ok", {**GOOD, "license": "LicenseRef-fan-work"}, "needs franchise"),
        (
            "ok",
            {
                **GOOD,
                "license": "LicenseRef-fan-work",
                "franchise": {"title": "Outer Wilds", "owner": "Mobius Digital"},
            },
            None,
        ),
        ("ok", {**GOOD, "ai_generated": False, "license": "MIT", "model": "x"}, "model: is only"),
        ("ok", {**GOOD, "technique": ["weaving"]}, "'weaving' is not in taxonomy.yaml"),
        ("ok", {**GOOD, "proposed_facets": {"technique": ["weaving"]}}, "proposed_facets"),
        ("ok", {**GOOD, "proposed_facets": {"technique": ["weaving"]}, "draft": True}, None),
        ("ok", {**GOOD, "draft": "false"}, "draft must be true or false, not 'false'"),
        ("ok", {**GOOD, "ai_generated": "yes"}, "ai_generated must be true or false"),
        ("ok", {**GOOD, "license": "CC0"}, "license 'CC0' has no LICENSES/CC0.txt"),
        (
            "ok",
            {**GOOD, "ai_generated": False, "license": "MIT"},
            "license 'MIT' has no LICENSES/MIT.txt",
        ),
    ],
)
def test_meta_rules(slug, meta, error, tmp_path, monkeypatch):
    monkeypatch.setattr(lint, "LICENSES", tmp_path)
    for name in ("CC0-1.0", "LicenseRef-fan-work"):
        (tmp_path / f"{name}.txt").write_text("licence text\n")
    errors, _ = lint.meta(slug, meta, TAXONOMY)
    if error is None:
        assert errors == []
    else:
        assert any(error in e for e in errors), errors


def test_meta_warnings():
    _, warnings = lint.meta(
        "ok",
        {**GOOD, "description": "A terracotta disc on a Black ground.", "themes": ["dark"]},
        None,
    )
    assert any("black, terracotta" in w for w in warnings)
    assert any("taxonomy.yaml not found" in w for w in warnings)
    assert any("needs the reason" in w for w in warnings)


def test_source_rules(tmp_path):
    path = tmp_path / "design.py"
    path.write_text(
        '"""A terracotta sun."""\n\nimport colorsys\nimport numpy.linalg\nimport requests\nfrom . import helper\n'
        "from walldye import ORANGE_DARK, luminance\n\n\ndef draw(s):\n    # ORANGE_DARK rim, a warm orange glow\n"
        "    return luminance(ORANGE_DARK)\n"
    )
    errors, warnings = lint.source(path)
    assert errors == [
        "line 5: imports requests; designs may import the standard library and walldye, numpy, scipy, shapely, skimage",
        "line 6: relative import; designs are single files",
    ]
    assert [w.split(":")[0] for w in warnings] == [
        "uses luminance",
        "uses colorsys",
        "colour words in docstrings or comments",
    ]
    assert "orange, terracotta (" in warnings[-1]


def test_svg_limits():
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    assert lint.svg(head + "</svg>") == ([], [])
    assert lint.svg(head + '<image href="x.png"/></svg>')[0] == [
        "<image> is not allowed: templates are self-contained vectors"
    ]
    errors, warnings = lint.svg(head + "<g/>" * 16_000 + "</svg>")
    assert errors == [] and warnings == [
        "16001 elements is heavy (over 15,000); merge shapes into one <path> per colour"
    ]
    errors, _ = lint.svg(head + "<g/>" * 20_000 + "</svg>")
    assert errors == [
        "20001 elements is over the limit of 20,000; merge shapes into one <path> per colour"
    ]
    errors, warnings = lint.svg(head + f'<path d="{"M0 0" * 160_000}"/></svg>')
    assert errors == [] and warnings[0].startswith("640,")
    assert lint.svg(head + f'<path d="{"M0 0" * 260_000}"/></svg>')[0][0].startswith("1,040,")
    assert lint.svg("<svg>")[0][0].startswith("invalid XML")


def test_near_clones(wallpapers, capsys):
    regen.install(wallpapers, "collision")
    regen.install(wallpapers, "collision", "copy")
    regen.install(wallpapers, "mask")
    built(capsys, "collision", "copy")
    check.near_clones(["copy", "mask"])
    assert (
        capsys.readouterr().out
        == "similar (1.00): collision ~ copy\nset: skipped, no build/16x9.svg: mask\n"
    )

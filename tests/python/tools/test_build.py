import json
import random

import numpy as np
import pytest
from fixtures import pieces
from tools_support import assert_recolors, built, legacy, seeds, versions

from walldye._aspect import SITE_ASPECTS, canvas_size
from walldye._theme import SEEDS
from walldye.tools import build, coefs, common, hashing, listing, review, themes
from walldye.tools.paths import template_name
from walldye.tools.themes import PRESETS
from walldye.tools.tokenize import find_colors

FIREPROOF = {k: PRESETS["fireproof"][k] for k in SEEDS}
ALL_HELD_OUT = themes.HELD_OUT["dark"] + themes.HELD_OUT["light"]


def slots(slug: str, variant: str = "default") -> dict[str, object]:
    s = build.load_slots(slug, variant)
    assert s is not None
    return s


# --- build output -----------------------------------------------------------------


def test_collision_builds_and_recolors(wallpapers, capsys):
    pieces.install(wallpapers, "collision")
    assert "collision: wrote 16x9.svg, slots.json" in built(capsys, "collision")
    b = common.build_dir("collision")
    assert sorted(p.name for p in b.iterdir()) == ["16x9.svg", "slots.json"]
    template = (b / "16x9.svg").read_text()
    assert template == common.render("collision", "fireproof")
    s = slots("collision")
    assert list(s) == [
        "design_sha",
        "focus",
        "cells",
        "probes",
        "render_lib",
        "checked",
        "16:9/dark",
        "16:9/light",
    ]
    assert s["design_sha"] == hashing.design_sha("collision")
    assert s["checked"] == build.version() == "0.2.0"
    assert s["render_lib"] == hashing.render_lib_sha()
    assert s["cells"] == [] and s["focus"] == [0.5, 0.5]
    assert s["probes"] == {
        "fireproof": hashing.sha256(template.encode()),
        **{
            r: hashing.sha256(common.render("collision", themes.SAMPLE[r]).encode())
            for r in ("dark", "light")
        },
    }
    table = build.entries(s)
    for regime in ("dark", "light"):
        entry = table[f"16:9/{regime}"]
        assert list(entry) == ["file", "sha256", "n", "coefs", "occ"]
        assert entry["file"] == "16x9.svg" and entry["sha256"] == hashing.sha256(template.encode())
        assert entry["n"] == len(entry["occ"]) == len(find_colors(template)) == 3
    for theme in pieces.RECOLOR_THEMES + ALL_HELD_OUT:
        assert_recolors("collision", theme)
    assert build.recolor(template, table["16:9/dark"], FIREPROOF) == template
    assert build.recolor(template, {**table["16:9/dark"], "n": 2}, seeds("nord")) == template


def test_recolor_evaluates_like_predict():
    r = random.Random(1)
    rows = [
        [round(r.uniform(-1, 1.5), 5) for _ in range(3)]
        + [round(r.uniform(-60, 60), 5) for _ in range(3)]
        for _ in range(40)
    ]
    template = "".join(f'<rect fill="#{i:06X}"/>' for i in range(40))
    entry: build.SlotsEntry = {
        "file": "",
        "sha256": "",
        "n": 40,
        "coefs": rows,
        "occ": list(range(40)),
    }
    for _ in range(20):
        theme = tuple(f"#{r.getrandbits(24):06X}" for _ in range(3))
        got = build.recolor(template, entry, dict(zip(SEEDS, theme, strict=True)))
        assert (coefs.colors(got) == coefs.predict(np.array(rows), theme)).all()


def test_select():
    both = {"16:9/dark": {}, "16:9/light": {}}
    assert build.select(both, "16:9", seeds("nord")) == "16:9/dark"
    assert build.select(both, "16:9", seeds("flexoki-light")) == "16:9/light"
    with pytest.raises(KeyError):
        build.select(both, "21:9", seeds("nord"))
    with pytest.raises(KeyError):
        build.select({"16:9/dark": {}}, "16:9", seeds("flexoki-light"))


def test_entries_are_validated():
    good = {"file": "16x9.svg", "sha256": "0", "n": 1, "coefs": [[1, 0, 0, 0, 0, 0]], "occ": [0]}
    assert build.entries({"design_sha": "x", "16:9/dark": good})["16:9/dark"]["coefs"] == [
        [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    ]
    for bad in ({**good, "occ": [1]}, {**good, "coefs": [[1, 2]]}, {**good, "n": "1"}, []):
        with pytest.raises(ValueError):
            build.entries({"16:9/dark": bad})


def test_light_branch_gets_its_own_template(wallpapers, capsys):
    pieces.install(wallpapers, "light-branch")
    built(capsys, "light-branch")
    table = build.entries(slots("light-branch"))
    assert table["16:9/dark"]["file"] == "16x9.svg"
    assert table["16:9/light"]["file"] == "16x9.light.svg"
    light = (common.build_dir("light-branch") / "16x9.light.svg").read_text()
    assert light == common.render("light-branch", "flexoki-light")
    assert "A100 100" not in light and "A100 100" in common.render("light-branch", "nord")
    for theme in ["solarized-light", "nord", *ALL_HELD_OUT]:
        assert_recolors("light-branch", theme)


def test_any_aspect_pixel_design(wallpapers, capsys):
    pieces.install(wallpapers, "pixels")
    out = built(capsys, "pixels")
    assert "pixel grid origin" in out
    b = common.build_dir("pixels")
    assert sorted(p.name for p in b.glob("*.svg")) == sorted(template_name(a) for a in SITE_ASPECTS)
    s = slots("pixels")
    table = build.entries(s)
    assert s["cells"] == [3]
    for aspect in SITE_ASPECTS:
        w, h = canvas_size(aspect)
        assert f'viewBox="0 0 {w} {h}"' in (b / template_name(aspect)).read_text()
        assert (
            table[f"{aspect}/dark"]["file"]
            == table[f"{aspect}/light"]["file"]
            == template_name(aspect)
        )
        assert_recolors("pixels", "nord", aspect)
    index = json.loads((wallpapers / "index.json").read_text())
    assert index["pixels"]["aspects"] == list(SITE_ASPECTS) and index["pixels"]["variants"] == {}


def test_legacy_piece_builds(wallpapers, capsys):
    legacy(wallpapers)
    built(capsys, "old")
    source = (wallpapers / "old/source.svg").read_text()
    assert (common.build_dir("old") / "16x9.svg").read_text() == source.replace(
        "#1c1b1a", "#1C1B1A"
    )
    for theme in ["nord", "flexoki-light", *ALL_HELD_OUT]:
        assert_recolors("old", theme)


# --- variants -------------------------------------------------------------------------


def test_variant_layout(wallpapers, capsys):
    versions(wallpapers)
    out = built(capsys, "versions")
    assert "versions (late): wrote late/16x9.svg, late/10x16.svg, late/slots.json" in out
    b = common.build_dir("versions")
    assert sorted(p.name for p in b.iterdir()) == [
        "10x16.svg",
        "16x9.svg",
        "bare",
        "late",
        "slots.json",
    ]
    for name in ("late", "bare"):
        assert sorted(p.name for p in (b / name).iterdir()) == [
            "10x16.svg",
            "16x9.svg",
            "slots.json",
        ]
        s = slots("versions", name)
        assert list(s)[:3] == ["design_sha", "variant", "focus"]
        assert s["variant"] == name and s["design_sha"] == hashing.design_sha("versions", name)
        assert build.entries(s)["16:9/dark"]["file"] == "16x9.svg"
        assert_recolors("versions", "nord", "10:16", name)
    assert "variant" not in slots("versions")
    assert (b / "late/16x9.svg").read_text() == common.render(
        "versions", "fireproof", variant="late"
    )
    index = json.loads((wallpapers / "index.json").read_text())
    assert index["versions"]["variants"] == {
        "late": {"draft": True, "label": "Eight o'clock"},
        "bare": {"draft": True, "label": "Five, no ring"},
    }
    assert "versions (bare): up to date" in built(capsys, "versions")


def test_variant_builds_touch_only_their_variant(wallpapers, capsys):
    versions(wallpapers)
    built(capsys, "versions")
    stray = common.build_dir("versions") / "gone"
    stray.mkdir()
    (common.build_dir("versions", "late") / "21x9.svg").write_text("<svg/>")
    out = built(capsys, "versions", variant="late", force=True)
    assert "versions (late): wrote" in out and "versions: wrote" not in out
    assert stray.exists() and not (common.build_dir("versions", "late") / "21x9.svg").exists()
    out = built(capsys, "versions")
    assert "removed build/gone/, not a declared variant" in out and not stray.exists()
    design = wallpapers / "versions/design.py"
    design.write_text(design.read_text().replace(', "bare": Clock(hour=5, ring=False, seed=3)', ""))
    meta = wallpapers / "versions/meta.yaml"
    meta.write_text(
        meta.read_text().replace("  bare:\n    label: Five, no ring\n    draft: true\n", "")
    )
    out = built(capsys, "versions")
    assert "removed build/bare/" in out and not common.build_dir("versions", "bare").exists()
    with pytest.raises(common.UsageError):
        build.run(["versions"], variant="bare")


def test_a_failing_variant_writes_nothing_for_the_piece(wallpapers, capsys):
    versions(wallpapers)
    design = wallpapers / "versions/design.py"
    design.write_text(
        design.read_text().replace(
            "    p = s.params\n",
            '    p = s.params\n    if p.hour == 8:\n        raise ValueError("late")\n',
        )
    )
    assert build.run(["versions"], jobs=1) == 1
    out = capsys.readouterr().out
    assert "draw failed: ValueError" in out and "versions: not written" in out
    assert not common.build_dir("versions").exists()


# --- check failures and skips ---------------------------------------------------------


def test_failed_check_writes_nothing(wallpapers, capsys):
    pieces.install(wallpapers, "unseeded")
    assert build.run(["unseeded"]) == 1
    assert "unseeded: not written" in capsys.readouterr().out
    assert not common.build_dir("unseeded").exists()


def old_render_lib(slug: str, **changes: object) -> None:
    """Make `slug`'s slots.json look built under other render inputs, with `changes`."""
    s = slots(slug)
    (common.build_dir(slug) / "slots.json").write_text(
        build.dump_slots({**s, "render_lib": "0" * 64, **changes})
    )


def test_skip_restamp_and_rebuild(wallpapers, capsys):
    pieces.install(wallpapers, "collision")
    built(capsys, "collision")
    assert "collision: up to date" in built(capsys, "collision")

    old_render_lib("collision")
    assert "probe renders unchanged" in built(capsys, "collision")
    assert slots("collision")["render_lib"] == hashing.render_lib_sha()
    assert "collision: up to date" in built(capsys, "collision")

    old_render_lib("collision", probes={**slots("collision")["probes"], "dark": "0"})
    assert "collision: wrote" in built(capsys, "collision")

    design = common.piece_dir("collision") / "design.py"
    design.write_text(design.read_text() + "\n\n# edited\n")
    assert "collision: wrote" in built(capsys, "collision")
    assert "collision: wrote" in built(capsys, "collision", force=True)

    template = common.build_dir("collision") / "16x9.svg"
    template.write_text(template.read_text() + "<!-- hand edit -->\n")
    assert "collision: wrote" in built(capsys, "collision")
    s = slots("collision")
    (common.build_dir("collision") / "slots.json").write_text(
        build.dump_slots({**s, "checked": "0.1.0"})
    )
    assert "collision: wrote" in built(capsys, "collision")
    assert "collision: up to date" in built(capsys, "collision")


def test_data_files_trigger_rebuilds(wallpapers, capsys):
    pieces.install(wallpapers, "data", data={"points.json": "[[960, 540]]\n"})
    built(capsys, "data")
    assert "data: up to date" in built(capsys, "data")
    (wallpapers / "data/data/points.json").write_text("[[100, 100], [960, 540]]\n")
    assert "data: wrote" in built(capsys, "data")


def test_build_applies_meta_rules_to_current_pieces(wallpapers, capsys):
    pieces.install(
        wallpapers, "collision", sources=[{"kind": "recreation", "title": "X"}], license="CC0-1.0"
    )
    built(capsys, "collision")
    meta = wallpapers / "collision/meta.yaml"
    meta.write_text(meta.read_text().replace("license: CC0-1.0\n", ""))
    assert build.run(["collision"]) == 1
    out = capsys.readouterr().out
    assert "recreation source needs an explicit license" in out and "collision: not written" in out


def test_unreadable_slots_json_is_rebuilt(wallpapers, capsys):
    pieces.install(wallpapers, "collision")
    built(capsys, "collision")
    path = common.build_dir("collision") / "slots.json"
    path.write_text("{x")
    out = built(capsys, "collision")
    assert f"collision: {path}: not valid JSON" in out and "collision: wrote" in out
    path.write_text("[]")
    assert "collision: wrote" in built(capsys, "collision", force=True)


def test_probe_failure_is_reported_and_the_run_goes_on(wallpapers, capsys):
    pieces.install(wallpapers, "collision")
    pieces.install(wallpapers, "collision", "other")
    built(capsys, all=True)
    old_render_lib("other")
    # design.py now fails to draw, but slots.json is made to look current for it
    design = wallpapers / "collision/design.py"
    design.write_text(design.read_text().replace("s.fill(P().rect(0, 0", 's.fill(P().rect(-1, "x"'))
    old_render_lib("collision", design_sha=hashing.design_sha("collision"))
    assert build.run([], all=True, jobs=1) == 1
    out = capsys.readouterr().out
    assert "draw failed: TypeError" in out and "collision: not written" in out
    assert "other: up to date (probe renders unchanged" in out


def test_unreadable_siblings_are_left_out(wallpapers, capsys):
    pieces.install(wallpapers, "collision")
    pieces.install(wallpapers, "collision", "syntax")
    (wallpapers / "syntax/design.py").write_text("def draw(s)\n    pass\n")
    pieces.install(wallpapers, "collision", "bad-yaml")
    (wallpapers / "bad-yaml/meta.yaml").write_text("title: [x\n")
    (wallpapers / "no-design").mkdir()
    (wallpapers / "no-design/meta.yaml").write_text("title: X\n")
    assert build.run(["collision"]) == 0
    captured = capsys.readouterr()
    assert "collision: wrote" in captured.out
    assert list(json.loads((wallpapers / "index.json").read_text())) == ["collision"]
    assert captured.err == ""  # unbuilt pieces are left out silently

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


def test_published_skips_drafts(wallpapers, capsys):
    pieces.install(wallpapers, "collision")
    versions(wallpapers, draft=False)
    out = built(capsys, all=True, published=True)
    assert "skipped 1 draft pieces" in out and not common.build_dir("collision").exists()
    assert [p.name for p in common.build_dir("versions").iterdir() if p.is_dir()] == []
    assert build.run(["collision"], published=True, jobs=1) == 2


def test_pool_builds_what_one_process_builds(wallpapers, capsys):
    pieces.install(wallpapers, "collision")
    versions(wallpapers)
    built(capsys, all=True, jobs=2)
    files = {
        p.relative_to(wallpapers): p.read_bytes() for p in wallpapers.rglob("*") if p.is_file()
    }
    built(capsys, all=True, force=True, jobs=1)
    again = {
        p.relative_to(wallpapers): p.read_bytes() for p in wallpapers.rglob("*") if p.is_file()
    }
    assert again == files


# --- index ----------------------------------------------------------------------------


def test_write_index(wallpapers, capsys):
    pieces.install(wallpapers, "collision", "plain")
    pieces.install(
        wallpapers,
        "collision",
        "recreation",
        draft=False,
        sources=[{"kind": "recreation", "title": "X"}],
        license="CC0-1.0",
    )
    pieces.install(wallpapers, "pixels", "unbuilt")
    pieces.install(wallpapers, "collision", "bad-meta")
    pieces.install(wallpapers, "collision", "bad-slots")
    built(capsys, "plain", "recreation", "bad-meta", "bad-slots")
    meta = wallpapers / "recreation/meta.yaml"
    meta.write_text(meta.read_text().replace("license: CC0-1.0\n", ""))
    (wallpapers / "bad-meta/meta.yaml").write_text("title: [x\n")
    (common.build_dir("bad-slots") / "slots.json").write_text("[]\n")
    build.write_index()
    bad_meta = wallpapers / "bad-meta/meta.yaml"
    bad_slots = common.build_dir("bad-slots") / "slots.json"
    yaml_error = "expected ',' or ']', but got '<stream end>'"
    assert capsys.readouterr().err.splitlines() == [
        f"index.json: left out bad-meta: {bad_meta}: not valid YAML (line 2): {yaml_error}",
        f"index.json: left out bad-slots: {bad_slots}: not a JSON object",
    ]
    assert json.loads((wallpapers / "index.json").read_text()) == {
        "plain": {
            "aspects": ["16:9"],
            "draft": True,
            "license": "CC0-1.0",
            "title": "Fixture",
            "variants": {},
        },
        "recreation": {
            "aspects": ["16:9"],
            "draft": False,
            "license": None,
            "title": "Fixture",
            "variants": {},
        },
    }

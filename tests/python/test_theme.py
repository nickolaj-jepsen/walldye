import importlib.util
import json
import random
import sys

import pytest
from conftest import IMPORT, NIXOS_BACKGROUNDS
from fixtures import regen
from PIL import Image

import walldye
from walldye import _basis, _theme
from walldye.tools import common

NORD = {"bg": "#2E3440", "fg": "#ECEFF4", "accent": "#88C0D0"}
FIREPROOF_SEEDS = {"bg": "#1C1B1A", "fg": "#DAD8CE", "accent": "#CF6A4C"}

# --- theme token grammar ------------------------------------------------------

TOKENS = json.loads((regen.HERE / "theme-tokens.json").read_text())


@pytest.mark.parametrize("case", TOKENS["valid"], ids=lambda c: repr(c["spec"]))
def test_valid_tokens(case):
    assert walldye.parse_seeds(case["spec"]) == case["seeds"]
    assert walldye.theme_token(walldye.parse_seeds(case["spec"])) == case["token"]


@pytest.mark.parametrize("spec", TOKENS["invalid"])
def test_invalid_tokens(spec):
    with pytest.raises(ValueError):
        walldye.parse_seeds(spec)
    with pytest.raises(ValueError):
        walldye.set_theme(spec)


def test_seed_dicts_are_validated():
    with pytest.raises(ValueError):
        walldye.set_theme({"bg": "#000", "fg": "#fff"})
    with pytest.raises(ValueError):
        walldye.set_theme({"bg": "#000", "fg": "#fff", "accent": "#f00", "accent_1": "#111"})
    with pytest.raises(ValueError):
        walldye.set_theme({"bg": "#000", "fg": "#fff", "accent": "red"})


def test_token_round_trips():
    for name in walldye.PRESETS:
        assert walldye.theme_token(walldye.parse_seeds(name)) == name
    r = random.Random(7)
    for _ in range(50):
        seeds = {k: f"#{r.getrandbits(24):06X}" for k in walldye.SEEDS}
        token = walldye.theme_token(seeds)
        assert walldye.parse_seeds(token) == seeds
        assert token == token.lower()


# --- fireproof and derive_theme ------------------------------------------------


@pytest.mark.parametrize(
    "spec",
    [
        "fireproof",
        "1c1b1a-dad8ce-cf6a4c",
        "1C1B1A,DAD8CE,CF6A4C",
        "bg=1c1b1a,fg=dad8ce,accent=cf6a4c",
    ],
)
def test_fireproof_seeds_resolve_to_pinned_table(spec):
    assert walldye.parse_theme(spec) == walldye.PRESETS["fireproof"]
    assert list(walldye.parse_theme(spec)) == list(walldye.TOKENS)


def test_fireproof_seed_dict_resolves_to_pinned_table():
    assert (
        walldye.set_theme({"bg": "#1c1b1a", "fg": "dad8ce", "accent": "#CF6A4C"})
        == walldye.PRESETS["fireproof"]
    )
    assert walldye.ACCENT_3 == "#71311E"


def test_fireproof_neighbour_is_derived():
    neighbour = walldye.parse_theme("1c1b1b-dad8ce-cf6a4c")
    assert neighbour == walldye.derive_theme({**FIREPROOF_SEEDS, "bg": "#1C1B1B"})
    assert neighbour["accent_3"] != walldye.PRESETS["fireproof"]["accent_3"]


def test_nord_regression():
    assert walldye.parse_theme("nord") == {
        "black": "#1A1E24", "bg_deep": "#272C36", "bg": "#2E3440", "bg_alt": "#3A404B", "ui": "#464C57",
        "ui_alt": "#525762", "ui_hi": "#696E78", "muted": "#999DA5", "fg_alt": "#C9CDD3", "fg": "#ECEFF4",
        "accent_hi": "#A4CDDA", "accent": "#88C0D0", "accent_1": "#79A8B8", "accent_2": "#719CAB",
        "accent_3": "#5B7A88", "accent_4": "#56727F", "accent_5": "#4B616E", "accent_6": "#40505D",
        "accent_7": "#37424E", "accent_8": "#323A46", "orange_dark": "#79A8B8",
    }  # fmt: skip


def test_nord_accents_rederive():
    t = walldye.parse_theme("nord")
    for k, frac in _theme._ACCENT_T.items():
        assert t[k] == walldye.mix(NORD["accent"], NORD["bg"], frac)
    assert t["orange_dark"] == t["accent_1"]


def test_mix_rounds_half_to_even():
    # Fireproof-derived accent_3 G = 106 + (27 - 106) * 0.5 = 66.5 -> 66, where JS Math.round gives 67.
    assert walldye.mix("#CF6A4C", "#1C1B1A", 0.5) == "#764233"
    assert walldye.derive_theme(FIREPROOF_SEEDS)["accent_3"] == "#764233"
    assert walldye.rgb_to_hex(0.5, 1.5, 2.5) == "#000202"


def test_is_light_tie_is_dark():
    assert not _theme.is_light("#808080", "#808080")
    assert _theme.is_light("#787878", "#777777")
    assert not _theme.is_light("#777777", "#787878")
    tie = walldye.derive_theme({"bg": "#808080", "fg": "#808080", "accent": "#808080"})
    assert tie["bg_deep"] == walldye.mix("#808080", "#000000", 0.15)
    walldye.set_theme("808080-808080-808080")
    assert not walldye.is_light()
    walldye.set_theme("flexoki-light")
    assert walldye.is_light()
    walldye.set_theme("solarized-light")
    assert walldye.is_light()
    walldye.set_theme("nord")
    assert not walldye.is_light()


BRANCH_LIB = IMPORT / "feat-wallgen-skill/scripts/wallgen.py"


@pytest.fixture
def branch(monkeypatch):
    """The feat/wallgen-skill library, imported from import/ (its glyphs import a top-level `font`)."""
    if not BRANCH_LIB.exists():
        pytest.skip("branch library not imported")
    monkeypatch.syspath_prepend(str(BRANCH_LIB.parent))
    spec = importlib.util.spec_from_file_location("_branch_wallgen", BRANCH_LIB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_derive_theme_matches_branch(branch):
    for name, seeds in walldye.PRESETS.items():
        # Presets added after the branch have no pinned tokens, so derive_theme is the reference.
        expected = (
            branch.parse_theme(name) if name in branch.PRESETS else branch.derive_theme(seeds)
        )
        assert walldye.parse_theme(name) == expected
    r = random.Random(11)
    triples = [tuple(f"#{r.getrandbits(24):06X}" for _ in range(3)) for _ in range(500)]
    triples += [
        ("#808080", "#808080", "#123456"),
        ("#777777", "#787878", "#ABCDEF"),
        ("#787878", "#777777", "#ABCDEF"),
    ]
    for bg, fg, accent in triples:
        seeds = {"bg": bg, "fg": fg, "accent": accent}
        assert walldye.derive_theme(seeds) == branch.derive_theme(seeds)


def test_pixel_helpers_match_branch_but_for_the_tag(branch):
    def draw(lib):
        s = lib.Svg()
        lib.grid_runs(
            s,
            [[0, 1, 2, 2], [1, 1, 0, 2]],
            [lib.BG, lib.UI, lib.ACCENT],
            3.5,
            10,
            20.5,
            opacity=0.5,
        )
        lib.sprite(s, "ab.\n.ba", {"a": lib.MUTED, "b": lib.ACCENT_2}, 4, x=7, y=9)
        lib.glyphs(
            s,
            ["ok ┌─┐", "⡇?"],
            lambda c, r, ch: lib.ACCENT if c % 2 else lib.UI,
            font="8x16",
            px=2,
            x=3,
            y=4,
        )
        lib.glyphs(s, ["FIG. 1"], lib.UI_HI, "5x8", 3, 100, 200, 1)
        return s.to_string()

    assert draw(walldye).replace(' class="px"', "") == draw(branch)
    assert draw(walldye).count(' class="px"') == 2 + 2 + 2 + 1


# --- aspects ----------------------------------------------------------------------


def test_site_aspect_canvases():
    sizes = {a: walldye.canvas_size(a) for a in walldye.SITE_ASPECTS}
    assert sizes == {
        "16:9": (1920, 1080),
        "16:10": (1728, 1080),
        "21:9": (2520, 1080),
        "32:9": (3840, 1080),
        "9:19.5": (1080, 2340),
        "10:16": (1080, 1728),
    }
    assert walldye.set_canvas("9:19.5") == (1080, 2340)
    assert (walldye.W, walldye.H) == (1080, 2340)


def test_supports_and_native_aspects():
    assert walldye.native_aspects(["any"]) == walldye.SITE_ASPECTS
    assert walldye.native_aspects(["16:9"]) == ["16:9"]
    assert walldye.native_aspects(["3440x1440", "10:16"]) == ["10:16"]  # 2.389 is 2.4% off 21:9
    assert walldye.native_aspects(["1366x768"]) == ["16:9"]  # 0.05% off
    assert walldye.supports(["16:9"], "1920x1080")
    assert not walldye.supports(["16:9"], "16:10")


@pytest.mark.parametrize(
    ("aspect", "light", "name"),
    [("16:9", False, "16x9.svg"), ("16:10", False, "16x10.svg"), ("21:9", True, "21x9.light.svg"),
     ("32:9", False, "32x9.svg"), ("9:19.5", True, "9x19.5.light.svg"), ("10:16", False, "10x16.svg")],
)  # fmt: skip
def test_template_names(aspect, light, name):
    assert walldye.template_name(aspect, light) == name
    assert walldye.parse_template_name(name) == (aspect, light)
    assert walldye.TEMPLATE_NAME.match(name)


@pytest.mark.parametrize(
    "name",
    [
        "16x9",
        "16x9.dark.svg",
        "slots.json",
        "16:9.svg",
        "x9.svg",
        "9x19.5.light.svg.bak",
        "16x9.light.light.svg",
    ],
)
def test_template_name_rejects(name):
    assert not walldye.TEMPLATE_NAME.match(name)
    with pytest.raises(ValueError):
        walldye.parse_template_name(name)


# --- pixel tagging ------------------------------------------------------------------


def test_pixel_paths_are_tagged_and_recorded():
    walldye.set_theme()
    s = walldye.Svg()
    walldye.grid_runs(
        s, [[0, 1, 1], [2, 0, 1]], [walldye.BG, walldye.UI, walldye.ACCENT], 4, 10, 20
    )
    walldye.sprite(s, "a.\n.b", {"a": walldye.UI, "b": walldye.ACCENT}, 3, x=1, y=2)
    walldye.glyphs(s, ["hi"], walldye.FG, px=2, x=5, y=6)
    walldye.glyphs(s, ["  "], walldye.FG, px=9)  # draws nothing, records nothing
    paths = [el for el in s.body if el.startswith("<path")]
    assert len(paths) == 5 and all(' class="px"' in p for p in paths)
    assert walldye.pixel_grids() == [(4, 10, 20), (3, 1, 2), (2, 5, 6)]
    walldye.set_canvas("21:9")
    assert walldye.pixel_grids() == []
    walldye.grid_runs(s, [[1]], [walldye.BG, walldye.UI], 5)
    walldye.set_theme("nord")
    assert walldye.pixel_grids() == []
    walldye.grid_runs(s, [[1]], [walldye.BG, walldye.UI], 5)
    walldye.reset_pixel_grids()
    assert walldye.pixel_grids() == []


def test_glyphs_key_keeps_roles_apart():
    def draw(**kw):
        s = walldye.Svg(bg=None)
        colour = {"a": walldye.UI, "b": walldye.ACCENT}
        walldye.glyphs(s, ["ab"], lambda c, r, ch: colour[ch], **kw)
        return s.body

    walldye.set_theme("fireproof")
    assert len(draw()) == len(draw(key=lambda c, r, ch: ch)) == 2
    walldye.set_theme("808080-808080-808080")  # every token collapses to one hex
    assert len(draw()) == 1
    assert len(draw(key=lambda c, r, ch: ch)) == 2
    walldye.set_theme("fireproof")
    with pytest.raises(ValueError):
        walldye.glyphs(
            walldye.Svg(),
            ["ab"],
            lambda c, r, ch: walldye.UI if ch == "a" else walldye.MUTED,
            key=lambda c, r, ch: 0,
        )


# --- fit basis ---------------------------------------------------------------------


def test_basis_is_the_documented_generation():
    assert _basis.generate(_basis.BASIS_SEED, 8) == _basis.BASIS
    assert _basis.generate(_basis.HELD_OUT_SEED, 4) == _basis._HELD_OUT_RANDOM
    for seed in range(_basis.BASIS_SEED):
        g = _basis.generate(seed, 8)
        assert max(_basis.condition_number(v) for v in g.values()) > _basis.MAX_COND


@pytest.mark.parametrize("regime", ["dark", "light"])
def test_basis_sets(regime):
    fireproof = tuple(FIREPROOF_SEEDS.values())
    assert len(_basis.BASIS[regime]) == 8
    assert _basis.condition_number(_basis.BASIS[regime]) <= _basis.MAX_COND
    themes = _basis.BASIS[regime] + _basis.HELD_OUT[regime] + _basis.PROBES[regime]
    assert all(_basis.regime(t) == regime for t in themes)
    assert all(walldye.theme_token(dict(zip(walldye.SEEDS, t))) != "fireproof" for t in themes)
    assert fireproof not in themes
    assert not set(_basis.BASIS[regime]) & set(_basis.HELD_OUT[regime] + _basis.PROBES[regime])
    presets = {
        n
        for n in walldye.PRESETS
        if n != "fireproof"
        and _theme.is_light(walldye.PRESETS[n]["bg"], walldye.PRESETS[n]["fg"])
        == (regime == "light")
    }
    assert presets <= {
        walldye.theme_token(dict(zip(walldye.SEEDS, t))) for t in _basis.HELD_OUT[regime]
    }
    assert len(_basis.HELD_OUT[regime]) == len(presets) + 4 + 4


def test_seed_matrix_shape():
    m = _basis.seed_matrix([("#FF0000", "#00FF00", "#0000FF")])
    assert m.tolist() == [[1, 0, 0, 1, 0, 0], [0, 1, 0, 0, 1, 0], [0, 0, 1, 0, 0, 1]]


# --- tools/common --------------------------------------------------------------------


def test_render_legacy(wallpapers):
    d = wallpapers / "old-piece"
    d.mkdir()
    (d / "source.svg").write_text(
        '<svg viewBox="0 0 1920 1080"><rect fill="#1c1b1a"/><path fill="#201a18" stroke="#CF6A4C"/>'
        '<mask id="c0ffee"><rect fill="white"/></mask><g mask="url(#c0ffee)" fill="#123456"/></svg>\n'
    )
    (d / "palette.yaml").write_text(
        '"#1C1B1A": bg\n"#cf6a4c": accent\n"#201A18": [bg_deep, accent_8, 0.68]\n"#C0FFEE": fg\n'
    )
    assert common.is_legacy("old-piece")
    assert common.design_aspects("old-piece") == ["16:9"]
    fire = common.render("old-piece", "fireproof")
    assert fire == (
        '<svg viewBox="0 0 1920 1080"><rect fill="#1C1B1A"/><path fill="#201A18" stroke="#CF6A4C"/>'
        '<mask id="c0ffee"><rect fill="white"/></mask><g mask="url(#c0ffee)" fill="#123456"/></svg>\n'
    )
    nord = common.render("old-piece", "nord")
    t = walldye.parse_theme("nord")
    assert f'fill="{t["bg"]}"' in nord and f'stroke="{t["accent"]}"' in nord
    assert f'fill="{walldye.mix(t["bg_deep"], t["accent_8"], 0.68)}"' in nord
    with pytest.raises(ValueError):
        common.render("old-piece", "nord", "21:9")


def test_render_design_and_aspects(wallpapers):
    d = wallpapers / "tiny"
    d.mkdir()
    (d / "design.py").write_text(
        "from dataclasses import dataclass\n\nfrom walldye import ACCENT, H, W, grid_runs, is_light\n\n"
        'ASPECTS: list[str] = ["any"]\n\n\n@dataclass\nclass Box:\n    w: int\n\n\n'
        "def draw(s):\n    s.rect(0, 0, Box(W).w / 2, H, fill=ACCENT if not is_light() else 'none')\n"
        "    grid_runs(s, [[1]], [None, ACCENT], 8, 16, 24)\n"
    )
    assert common.design_aspects("tiny") == ["any"]
    svg = common.render("tiny", "nord", "10:16")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1728"')
    assert '<rect x="0" y="0" width="540" height="1728" fill="#88C0D0"/>' in svg
    assert walldye.pixel_grids() == [(8, 16, 24)]
    assert "_walldye_tiny" not in sys.modules
    assert not (d / "__pycache__").exists()
    (d / "design.py").write_text("def draw(s):\n    pass\n")
    assert common.design_aspects("tiny") == ["16:9"]
    (d / "design.py").write_text("ASPECTS = list(('any',))\n")
    with pytest.raises(ValueError):
        common.design_aspects("tiny")
    with pytest.raises(ValueError):
        common.piece_dir("../etc")


def test_rasterise_ink_and_focus():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" width="200" height="100"><rect x="0" y="0" width="200" height="100" fill="#000000"/><rect x="150" y="0" width="50" height="50" fill="#FFFFFF"/></svg>'
    img = common.rasterise(svg, 100)
    assert img.mode == "RGB" and img.size == (100, 50)
    assert common.focus(img, "#000000") == (0.875, 0.25)
    assert common.focus(Image.new("RGB", (10, 10)), "#000000") == (0.5, 0.5)
    crop = common.rasterise(svg, 40, crop=(100, 0, 100, 100))
    assert crop.size == (40, 40)
    m = common.ink_map(img, "#000000")
    assert m.shape == (64 * 36,) and abs((m @ m) - 1) < 1e-9


# --- byte-for-byte with the nixos toolkit ------------------------------------------

SCHOTTER = IMPORT / "nixos-wallgen/wallgen/designs/schotter.py"


@pytest.mark.skipif(
    not (SCHOTTER.exists() and (NIXOS_BACKGROUNDS / "schotter.svg").exists()),
    reason="nixos schotter not available",
)
def test_schotter_reproduces_nixos_svg(wallpapers):
    (wallpapers / "schotter").mkdir()
    (wallpapers / "schotter" / "design.py").write_text(
        SCHOTTER.read_text().replace("from wallgen import", "from walldye import")
    )
    assert (
        common.render("schotter", "fireproof") == (NIXOS_BACKGROUNDS / "schotter.svg").read_text()
    )

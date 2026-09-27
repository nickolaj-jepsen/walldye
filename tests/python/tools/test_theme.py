import json
import random

import pytest
from fixtures import regen
from PIL import Image

from walldye import _check_themes, _theme
from walldye._aspect import (
    SITE_ASPECTS,
    TEMPLATE_NAME,
    canvas_size,
    native_aspects,
    parse_template_name,
    supports,
    template_name,
)
from walldye._theme import (
    PRESETS,
    SEEDS,
    TOKENS,
    derive_theme,
    mix,
    parse_seeds,
    parse_theme,
    theme_token,
)
from walldye.tools import common

NORD = {"bg": "#2E3440", "fg": "#ECEFF4", "accent": "#88C0D0"}
FIREPROOF_SEEDS = {"bg": "#1C1B1A", "fg": "#DAD8CE", "accent": "#CF6A4C"}

# --- theme token grammar ------------------------------------------------------

TOKEN_SPEC = json.loads((regen.SHARED / "theme-tokens.json").read_text())


@pytest.mark.parametrize("case", TOKEN_SPEC["valid"], ids=lambda c: repr(c["spec"]))
def test_valid_tokens(case):
    assert parse_seeds(case["spec"]) == case["seeds"]
    assert theme_token(parse_seeds(case["spec"])) == case["token"]


@pytest.mark.parametrize("spec", TOKEN_SPEC["invalid"])
def test_invalid_tokens(spec):
    with pytest.raises(ValueError):
        parse_seeds(spec)
    with pytest.raises(ValueError):
        common.tokens_of(spec)


def test_seed_dicts_are_validated():
    with pytest.raises(KeyError):
        common.tokens_of({"bg": "#000", "fg": "#fff"})
    with pytest.raises(ValueError):
        _theme.theme_tokens({"bg": "#000", "fg": "#fff", "accent": "#f00", "accent_1": "#111"})
    with pytest.raises(ValueError):
        common.tokens_of({"bg": "#000", "fg": "#fff", "accent": "red"})


def test_token_round_trips():
    for name in PRESETS:
        assert theme_token(parse_seeds(name)) == name
    r = random.Random(7)
    for _ in range(50):
        seeds = {k: f"#{r.getrandbits(24):06X}" for k in SEEDS}
        token = theme_token(seeds)
        assert parse_seeds(token) == seeds
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
    assert parse_theme(spec) == PRESETS["fireproof"]
    assert list(parse_theme(spec)) == list(TOKENS)


def test_fireproof_seed_dict_resolves_to_pinned_table():
    tokens = common.tokens_of({"bg": "#1c1b1a", "fg": "dad8ce", "accent": "#CF6A4C"})
    assert tokens == PRESETS["fireproof"] and tokens["accent_3"] == "#71311E"


def test_fireproof_neighbour_is_derived():
    neighbour = parse_theme("1c1b1b-dad8ce-cf6a4c")
    assert neighbour == derive_theme({**FIREPROOF_SEEDS, "bg": "#1C1B1B"})
    assert neighbour["accent_3"] != PRESETS["fireproof"]["accent_3"]


def test_nord_regression():
    assert parse_theme("nord") == {
        "black": "#1A1E24", "bg_deep": "#272C36", "bg": "#2E3440", "bg_alt": "#3A404B", "ui": "#464C57",
        "ui_alt": "#525762", "ui_hi": "#696E78", "muted": "#999DA5", "fg_alt": "#C9CDD3", "fg": "#ECEFF4",
        "accent_hi": "#A4CDDA", "accent": "#88C0D0", "accent_1": "#79A8B8", "accent_2": "#719CAB",
        "accent_3": "#5B7A88", "accent_4": "#56727F", "accent_5": "#4B616E", "accent_6": "#40505D",
        "accent_7": "#37424E", "accent_8": "#323A46", "orange_dark": "#79A8B8",
    }  # fmt: skip


def test_nord_accents_rederive():
    t = parse_theme("nord")
    for k, frac in _theme._ACCENT_T.items():
        assert t[k] == mix(NORD["accent"], NORD["bg"], frac)
    assert t["orange_dark"] == t["accent_1"]


def test_mix_rounds_half_to_even():
    # Fireproof-derived accent_3 G = 106 + (27 - 106) * 0.5 = 66.5 -> 66, where JS Math.round gives 67.
    assert mix("#CF6A4C", "#1C1B1A", 0.5) == "#764233"
    assert derive_theme(FIREPROOF_SEEDS)["accent_3"] == "#764233"
    assert _theme.rgb_to_hex(0.5, 1.5, 2.5) == "#000202"


def test_is_light_tie_is_dark():
    assert not _theme.is_light("#808080", "#808080")
    assert _theme.is_light("#787878", "#777777")
    assert not _theme.is_light("#777777", "#787878")
    tie = derive_theme({"bg": "#808080", "fg": "#808080", "accent": "#808080"})
    assert tie["bg_deep"] == mix("#808080", "#000000", 0.15)
    assert common.regime_of("808080-808080-808080") == "dark"
    assert common.regime_of("flexoki-light") == common.regime_of("solarized-light") == "light"
    assert common.regime_of("nord") == "dark"


def test_token_coefs_are_derive_theme_before_rounding():
    r = random.Random(7)
    for _ in range(200):
        seeds = {k: f"#{r.getrandbits(24):06X}" for k in SEEDS}
        light = _theme.is_light(seeds["bg"], seeds["fg"])
        rgb = {k: _theme.hex_to_rgb(v) for k, v in seeds.items()}
        for name, got in derive_theme(seeds).items():
            a, b, c, *d = _theme.token_coefs(name, light)
            want = [
                a * rgb["bg"][i] + b * rgb["fg"][i] + c * rgb["accent"][i] + d[i] for i in range(3)
            ]
            # derive_theme rounds once, so each channel is within half a unit (plus float noise).
            assert all(abs(g - w) <= 0.5 + 1e-9 for g, w in zip(_theme.hex_to_rgb(got), want)), name


# --- aspects ----------------------------------------------------------------------


def test_site_aspect_canvases():
    assert {a: canvas_size(a) for a in SITE_ASPECTS} == {
        "16:9": (1920, 1080),
        "16:10": (1728, 1080),
        "21:9": (2520, 1080),
        "32:9": (3840, 1080),
        "9:19.5": (1080, 2340),
        "10:16": (1080, 1728),
    }
    for good in ("16:9", "3440x1440", "9:19.5"):
        assert common.is_aspect(good)
    for bad in ("wide", "inf:1", "16:-9", "16:0"):
        assert not common.is_aspect(bad)


def test_supports_and_native_aspects():
    assert native_aspects("any") == SITE_ASPECTS
    assert native_aspects(("16:9",)) == ("16:9",)
    assert native_aspects(("10:16",)) == ("16:9", "10:16")
    assert supports(("16:9",), "1920x1080")
    assert not supports(("16:9",), "16:10")


@pytest.mark.parametrize(
    ("aspect", "light", "name"),
    [("16:9", False, "16x9.svg"), ("16:10", False, "16x10.svg"), ("21:9", True, "21x9.light.svg"),
     ("32:9", False, "32x9.svg"), ("9:19.5", True, "9x19.5.light.svg"), ("10:16", False, "10x16.svg")],
)  # fmt: skip
def test_template_names(aspect, light, name):
    assert template_name(aspect, light) == name
    assert parse_template_name(name) == (aspect, light)
    assert TEMPLATE_NAME.fullmatch(name)


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
        "16x9.svg\n",
    ],
)
def test_template_name_rejects(name):
    assert not TEMPLATE_NAME.fullmatch(name)
    with pytest.raises(ValueError):
        parse_template_name(name)


# --- check themes ------------------------------------------------------------------


def test_held_out_is_the_documented_generation():
    assert _check_themes.generate(_check_themes.HELD_OUT_SEED, 4) == _check_themes._HELD_OUT_RANDOM


@pytest.mark.parametrize("regime", ["dark", "light"])
def test_check_theme_sets(regime):
    fireproof = tuple(FIREPROOF_SEEDS.values())
    themes = _check_themes.HELD_OUT[regime] + _check_themes.PROBES[regime]
    assert all(_check_themes.regime(t) == regime for t in themes)
    assert all(theme_token(dict(zip(SEEDS, t, strict=True))) != "fireproof" for t in themes)
    assert fireproof not in themes
    assert _check_themes.SAMPLE[regime] in _check_themes.HELD_OUT[regime]
    presets = {
        n
        for n in PRESETS
        if n != "fireproof"
        and _theme.is_light(PRESETS[n]["bg"], PRESETS[n]["fg"]) == (regime == "light")
    }
    assert presets <= {
        theme_token(dict(zip(SEEDS, t, strict=True))) for t in _check_themes.HELD_OUT[regime]
    }
    assert len(_check_themes.HELD_OUT[regime]) == len(presets) + 4 + 4


# --- rasterising -------------------------------------------------------------------


def test_rasterise_ink_and_focus():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" width="200" height="100">'
        '<rect x="0" y="0" width="200" height="100" fill="#000000"/>'
        '<rect x="150" y="0" width="50" height="50" fill="#FFFFFF"/></svg>'
    )
    img = common.rasterise(svg, 100)
    assert img.mode == "RGB" and img.size == (100, 50)
    assert common.focus(img, "#000000") == (0.875, 0.25)
    assert common.focus(Image.new("RGB", (10, 10)), "#000000") == (0.5, 0.5)
    assert common.rasterise(svg, 40, crop=(100, 0, 100, 100)).size == (40, 40)
    m = common.ink_map(img, "#000000")
    assert m.shape == (64 * 36,) and abs((m @ m) - 1) < 1e-9
    assert common.viewbox(svg) == "0 0 200 100" and common.viewbox("<svg/>") is None
    assert common.crop_svg(svg, (10, 20, 30, 40)).startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 30 40" width="30" height="40">'
    )


def test_background_is_the_rect_after_the_defs():
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 9" width="16" height="9">\n'
    rect = '<rect x="0" y="0" width="16" height="9" fill="#100F0F"/>\n'
    mask = '<defs><mask id="m1"><rect x="0" y="0" width="16" height="9" fill="#FFFFFF"/>'
    assert common.background(head + rect + "</svg>\n") == "#100F0F"
    assert common.background(head + mask + "</mask></defs>\n" + rect + "</svg>\n") == "#100F0F"
    assert common.background(head + '<path d="M0 0H9"/>\n' + rect) == common.FIREPROOF_BG

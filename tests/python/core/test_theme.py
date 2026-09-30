import random

import pytest

from walldye import _theme
from walldye._aspect import SITE_ASPECTS, canvas_size, native_aspects, supports
from walldye._theme import SEEDS, TOKENS, derive_theme, mix
from walldye.tools import paths, themes
from walldye.tools.themes import PRESETS, parse_theme

NORD = {"bg": "#2E3440", "fg": "#ECEFF4", "accent": "#88C0D0"}
FIREPROOF_SEEDS = {"bg": "#1C1B1A", "fg": "#DAD8CE", "accent": "#CF6A4C"}

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
    tokens = themes.tokens_of({"bg": "#1c1b1a", "fg": "dad8ce", "accent": "#CF6A4C"})
    assert tokens == PRESETS["fireproof"] and tokens["accent_3"] == "#71311E"


def test_fireproof_neighbor_is_derived():
    neighbor = parse_theme("1c1b1b-dad8ce-cf6a4c")
    assert neighbor == derive_theme({**FIREPROOF_SEEDS, "bg": "#1C1B1B"})
    assert neighbor["accent_3"] != PRESETS["fireproof"]["accent_3"]


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
    assert themes.regime_of("808080-808080-808080") == "dark"
    assert themes.regime_of("flexoki-light") == themes.regime_of("solarized-light") == "light"
    assert themes.regime_of("nord") == "dark"


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
        assert paths.is_aspect(good)
    for bad in ("wide", "inf:1", "16:-9", "16:0"):
        assert not paths.is_aspect(bad)


def test_supports_and_native_aspects():
    assert native_aspects("any") == SITE_ASPECTS
    assert native_aspects(("16:9",)) == ("16:9",)
    assert native_aspects(("10:16",)) == ("16:9", "10:16")
    assert supports(("16:9",), "1920x1080")
    assert not supports(("16:9",), "16:10")

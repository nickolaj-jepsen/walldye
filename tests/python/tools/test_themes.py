import json
import random

import pytest

from walldye import _theme
from walldye._theme import SEEDS
from walldye.tools import common, themes
from walldye.tools.themes import PRESETS, parse_seeds, theme_token

NORD = {"bg": "#2E3440", "fg": "#ECEFF4", "accent": "#88C0D0"}
FIREPROOF_SEEDS = {"bg": "#1C1B1A", "fg": "#DAD8CE", "accent": "#CF6A4C"}

# --- theme token grammar ------------------------------------------------------

TOKEN_SPEC = json.loads((common.ROOT / "src/lib/__fixtures__/theme-tokens.json").read_text())


@pytest.mark.parametrize("case", TOKEN_SPEC["valid"], ids=lambda c: repr(c["spec"]))
def test_valid_tokens(case):
    assert parse_seeds(case["spec"]) == case["seeds"]
    assert theme_token(parse_seeds(case["spec"])) == case["token"]


@pytest.mark.parametrize("spec", TOKEN_SPEC["invalid"])
def test_invalid_tokens(spec):
    with pytest.raises(ValueError):
        parse_seeds(spec)
    with pytest.raises(ValueError):
        themes.tokens_of(spec)


def test_seed_dicts_are_validated():
    with pytest.raises(KeyError):
        themes.tokens_of({"bg": "#000", "fg": "#fff"})
    with pytest.raises(ValueError):
        _theme.theme_tokens({"bg": "#000", "fg": "#fff", "accent": "#f00", "accent_1": "#111"})
    with pytest.raises(ValueError):
        themes.tokens_of({"bg": "#000", "fg": "#fff", "accent": "red"})


def test_token_round_trips():
    for name in PRESETS:
        assert theme_token(parse_seeds(name)) == name
    r = random.Random(7)
    for _ in range(50):
        seeds = {k: f"#{r.getrandbits(24):06X}" for k in SEEDS}
        token = theme_token(seeds)
        assert parse_seeds(token) == seeds
        assert token == token.lower()


# --- check themes ------------------------------------------------------------------


def test_held_out_is_the_documented_generation():
    assert themes.generate(themes.HELD_OUT_SEED, 4) == themes._HELD_OUT_RANDOM


@pytest.mark.parametrize("regime", ["dark", "light"])
def test_check_theme_sets(regime):
    fireproof = tuple(FIREPROOF_SEEDS.values())
    held = themes.HELD_OUT[regime] + themes.PROBES[regime]
    assert all(_theme.regime(t.bg, t.fg) == regime for t in held)
    assert all(theme_token(dict(zip(SEEDS, t, strict=True))) != "fireproof" for t in held)
    assert fireproof not in held
    assert themes.SAMPLE[regime] in themes.HELD_OUT[regime]
    presets = {
        n
        for n in PRESETS
        if n != "fireproof"
        and _theme.is_light(PRESETS[n]["bg"], PRESETS[n]["fg"]) == (regime == "light")
    }
    assert presets <= {
        theme_token(dict(zip(SEEDS, t, strict=True))) for t in themes.HELD_OUT[regime]
    }
    assert len(themes.HELD_OUT[regime]) == len(presets) + 4 + 4

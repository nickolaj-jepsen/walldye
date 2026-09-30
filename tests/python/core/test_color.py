import copy
import os
import pickle
import random
import subprocess
import sys

import numpy as np
import pytest

import walldye
from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    BG_ALT,
    FG,
    MASK_BLACK,
    MASK_WHITE,
    MUTED,
    UI,
    Color,
    Ladder,
    MaskColor,
    _theme,
    by_regime,
    ladder,
    mix,
    ramp,
)
from walldye._color import resolve, token
from walldye.tools.themes import PRESETS, parse_theme

TOKEN_NAMES = [t for t in _theme.TOKENS if t != "orange_dark"]


def all_themes() -> list[dict[str, str]]:
    """Every preset plus seeded random themes of both regimes."""
    r = random.Random(11)
    randoms = [
        {k: f"#{r.getrandbits(24):06X}" for k in _theme.SEEDS}
        for _ in range(40)  # both regimes turn up in 40 draws
    ]
    return [parse_theme(name) for name in PRESETS] + [_theme.theme_tokens(s) for s in randoms]


THEMES = all_themes()


def test_tokens_are_exported_constants():
    for name in TOKEN_NAMES:
        c = getattr(walldye, name.upper())
        assert isinstance(c, Color)
        assert c is token(name)
        assert repr(c) == name.upper()
    assert not hasattr(walldye, "ORANGE_DARK")
    assert repr(token("orange_dark")) == "ORANGE_DARK"
    with pytest.raises(ValueError, match="unknown token"):
        token("purple")


def test_equality_and_hash_follow_the_formula():
    a, b = mix(UI, BG_ALT, 0.5), mix(UI, BG_ALT, 0.5)
    assert a == b and hash(a) == hash(b) and a is not b
    assert mix(UI, BG_ALT, 0.5) != mix(BG_ALT, UI, 0.5)
    assert mix(UI, BG_ALT, 0.5) != mix(UI, BG_ALT, 0.25)
    assert by_regime(UI, MUTED) == by_regime(UI, MUTED) != by_regime(MUTED, UI)
    assert {a: 1}[b] == 1
    assert len({UI, token("ui"), mix(UI, UI, 0.3)}) == 1
    assert MASK_WHITE != mix(UI, BG, 0.5)
    assert (UI == "ui") is False
    assert UI.__eq__(MASK_WHITE) is NotImplemented


def test_mix_numpy_amount_is_stored_as_float():
    assert mix(UI, BG, np.float64(0.5)) == mix(UI, BG, 0.5)
    assert mix(UI, BG, np.float32(0.5)) == mix(UI, BG, 0.5)
    assert mix(UI, BG, 1) is BG


HASH_SCRIPT = """
from walldye import ACCENT, BG, MASK_WHITE, MASK_BLACK, UI, by_regime, mix
cs = [mix(UI, BG, k / 10) for k in range(1, 10)]
cs += [by_regime(UI, ACCENT), mix(MASK_BLACK, MASK_WHITE, 0.3)]
print([hash(c) for c in cs])
print([repr(c) for c in set(cs)])
"""


def run_hashes(seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    return subprocess.run(
        [sys.executable, "-c", HASH_SCRIPT], capture_output=True, text=True, check=True, env=env
    ).stdout


def test_hashes_and_set_order_do_not_depend_on_the_hash_seed():
    assert run_hashes("1") == run_hashes("4242") == run_hashes("99")


def test_colors_have_no_order():
    for op in ("__lt__", "__le__", "__gt__", "__ge__"):
        with pytest.raises(TypeError, match="colors have no order"):
            getattr(UI, op)(BG)
    with pytest.raises(TypeError, match="colors have no order"):
        sorted([UI, BG])
    with pytest.raises(TypeError):
        sorted([MASK_WHITE, MASK_BLACK])


def test_colors_have_no_text_form():
    c = mix(UI, BG_ALT, 0.5)
    msg = r"a Color has no text form; pass it to a drawing call \(got mix\(UI, BG_ALT, 0\.5\)\)"
    with pytest.raises(TypeError, match=msg):
        str(c)
    with pytest.raises(TypeError, match=msg):
        f"{c}"
    with pytest.raises(TypeError, match=msg):
        format(c, "")
    with pytest.raises(TypeError, match="a MaskColor has no text form"):
        str(MASK_WHITE)


def test_colors_are_immutable_and_pickle():
    c = mix(UI, by_regime(ACCENT, FG), 0.25)
    with pytest.raises(AttributeError):
        c._formula = (0, 1)
    with pytest.raises(AttributeError):
        del c._formula
    for twin in (pickle.loads(pickle.dumps(c)), copy.copy(c), copy.deepcopy(c)):
        assert twin == c and hash(twin) == hash(c) and type(twin) is Color
    assert pickle.loads(pickle.dumps(MASK_WHITE)) == MASK_WHITE


def test_canonical_forms():
    assert mix(UI, BG, 0) is UI
    assert mix(UI, BG, 1) is BG
    assert mix(UI, UI, 0.4) is UI
    assert mix(UI, BG, 0) == UI
    assert mix(MASK_BLACK, MASK_WHITE, 1) is MASK_WHITE
    for tokens in THEMES:
        for a, b in ((UI, BG), (ACCENT, FG)):
            ha, hb = resolve(a, tokens), resolve(b, tokens)
            assert resolve(mix(a, b, 0), tokens) == _theme.mix(ha, hb, 0)
            assert resolve(mix(a, b, 1), tokens) == _theme.mix(ha, hb, 1)
        assert resolve(mix(UI, UI, 0.37), tokens) == _theme.mix(tokens["ui"], tokens["ui"], 0.37)


@pytest.mark.parametrize("t", [1.7, -0.1, float("nan"), float("inf")])
def test_mix_amount_outside_the_unit_interval(t):
    with pytest.raises(ValueError, match=r"mix t must be within \[0, 1\]"):
        mix(UI, BG, t)


def test_mix_errors():
    with pytest.raises(ValueError, match=r"mix t must be within \[0, 1\], got 1\.7"):
        mix(UI, BG, 1.7)
    with pytest.raises(TypeError):
        mix(UI, BG, True)
    with pytest.raises(TypeError):
        mix(UI, BG, "0.5")
    with pytest.raises(TypeError, match="raw color strings"):
        mix("#FF0000", BG, 0.5)
    with pytest.raises(TypeError, match="Color with a MaskColor"):
        mix(UI, MASK_WHITE, 0.5)
    with pytest.raises(TypeError):
        mix(UI, None, 0.5)


def test_ramp():
    assert ramp(UI, BG, 1) == [UI]
    assert ramp(UI, BG, 5) == [UI, mix(UI, BG, 0.25), mix(UI, BG, 0.5), mix(UI, BG, 0.75), BG]
    assert ramp(MASK_BLACK, MASK_WHITE, 3)[1] == mix(MASK_BLACK, MASK_WHITE, 0.5)
    with pytest.raises(ValueError):
        ramp(UI, BG, 0)
    with pytest.raises(TypeError):
        ramp(UI, BG, 2.0)
    with pytest.raises(TypeError, match="Color with a MaskColor"):
        ramp(UI, MASK_WHITE, 3)
    with pytest.raises(TypeError, match="raw color strings"):
        ramp(UI, "#FFF", 3)


def v1_accent_ramp(tokens: dict[str, str], n: int, lo: str, hi: str) -> list[str]:
    """v1's accent_ramp(n, lo, hi), the formula ladder((lo, ACCENT_4, hi), n) replaces."""
    mid = tokens["accent_4"]
    out = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 1.0
        out.append(
            _theme.mix(lo, mid, t / 0.5) if t < 0.5 else _theme.mix(mid, hi, (t - 0.5) / 0.5)
        )
    return out


def test_ladder_resolves_like_v1_accent_ramp():
    for tokens in THEMES:
        for n in range(2, 13):
            for lo, hi in ((BG, ACCENT), (UI, FG), (BG_ALT, ACCENT)):
                want = v1_accent_ramp(tokens, n, resolve(lo, tokens), resolve(hi, tokens))
                assert [resolve(c, tokens) for c in ladder((lo, ACCENT_4, hi), n)] == want


def test_ladder_shape_and_errors():
    tones = ladder((ACCENT_4, UI, BG_ALT), 5)
    assert isinstance(tones, Ladder) and isinstance(tones, tuple) and len(tones) == 5
    assert tones[0] is ACCENT_4 and tones[2] is UI and tones[-1] is BG_ALT
    assert tones[1] == mix(ACCENT_4, UI, 0.5)
    assert tones[1:3] == (mix(ACCENT_4, UI, 0.5), UI)
    assert ladder((UI, BG), 2) == (UI, BG)
    with pytest.raises(ValueError):
        ladder((UI,), 4)
    with pytest.raises(ValueError):
        ladder((UI, BG), 1)
    with pytest.raises(TypeError):
        ladder((MASK_BLACK, MASK_WHITE), 3)
    with pytest.raises(TypeError, match="raw color strings"):
        ladder(("#000", BG), 3)


def test_ladder_rung_and_at():
    tones = ladder((UI, BG), 4)
    assert [tones.rung(v) for v in (-1, 0, 0.24, 0.25, 0.5, 0.99, 1, 7)] == [0, 0, 0, 1, 2, 3, 3, 3]
    assert tones.rung(np.float64(0.6)) == 2
    v = np.array([-0.5, 0.0, 0.3, 0.75, 1.0, 2.0])
    got = tones.rung(v)
    assert got.dtype == np.int64
    assert got.tolist() == [tones.rung(float(x)) for x in v]
    assert tones.at(0.3) is tones[1]
    with pytest.raises(TypeError):
        tones.rung(True)
    with pytest.raises(ValueError):
        tones.rung(float("nan"))
    with pytest.raises(ValueError, match="NaN"):
        tones.rung(np.array([np.nan, 0.5]))


def test_by_regime():
    c = by_regime(UI, MUTED)
    assert by_regime(UI, UI) is UI
    for tokens in THEMES:
        light = _theme.is_light(tokens["bg"], tokens["fg"])
        assert resolve(c, tokens) == tokens["muted" if light else "ui"]
        nested = mix(c, BG, 0.3)
        assert resolve(nested, tokens) == _theme.mix(resolve(c, tokens), tokens["bg"], 0.3)
    with pytest.raises(TypeError):
        by_regime(MASK_WHITE, MASK_BLACK)
    with pytest.raises(TypeError, match="raw color strings"):
        by_regime("#000", UI)
    assert repr(c) == "by_regime(UI, MUTED)"


def test_resolve_equals_theme_mix_chains():
    r = random.Random(5)
    for tokens in THEMES:
        for _ in range(30):
            a, b, c = (r.choice(TOKEN_NAMES) for _ in range(3))
            t1, t2 = r.random(), r.random()
            ca, cb, cc = token(a), token(b), token(c)
            want = _theme.mix(tokens[a], tokens[b], t1) if a != b else tokens[a]
            assert resolve(mix(ca, cb, t1), tokens) == want
            want2 = _theme.mix(want, tokens[c], t2)
            assert resolve(mix(mix(ca, cb, t1), cc, t2), tokens) == want2


def test_mask_colors_resolve_to_constants():
    gray = mix(MASK_BLACK, MASK_WHITE, 0.4)
    assert isinstance(gray, MaskColor)
    for tokens in THEMES:
        assert resolve(MASK_WHITE, tokens) == "#FFFFFF"
        assert resolve(MASK_BLACK, tokens) == "#000000"
        assert resolve(gray, tokens) == "#666666"
    assert repr(gray) == "mix(MASK_BLACK, MASK_WHITE, 0.4)"

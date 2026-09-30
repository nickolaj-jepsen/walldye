import importlib.util
import json

from walldye._aspect import SITE_ASPECTS
from walldye._theme import PRESETS, TOKENS, derive_theme, parse_theme
from walldye.tools import common

_spec = importlib.util.spec_from_file_location("regen", common.ROOT / "scripts/fixtures/regen.py")
assert _spec is not None and _spec.loader is not None
regen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regen)


def test_themes_fixture():
    fx = regen.themes()
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


def test_crops_fixture_boxes_sit_at_their_position():
    cw, ch = 1920, 1080
    crops = regen.crops()
    assert {c["aspect"] for c in crops} == set(SITE_ASPECTS) - {"16:9"}
    for c in crops:
        x, y, w, h = c["box"]
        moving, room = (x, cw - w) if w < cw else (y, ch - h)
        assert 0 <= c["t"] <= 1 and abs(moving - c["t"] * room) < 1e-9

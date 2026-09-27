import numpy as np
import pytest
from fixtures import regen

from walldye import _basis
from walldye.tools import check, common, fit
from walldye.tools.tokenize import find_colours


def test_fit_recovers_linear_slots():
    truth = np.array([
        [1, 0, 0, 0, 0, 0],
        [0.5, 0.5, 0, 0, 0, 0],
        [0, 0, 0.3, 10, 20, 30],
        [0, 0, 0, 255, 255, 255],
        [0.2, -0.1, 0.6, 5, 0, -5],
    ])  # fmt: skip
    for regime in ("dark", "light"):
        basis = _basis.BASIS[regime]
        coefs = fit.fit(basis, [fit.predict(truth, t) for t in basis])
        assert np.allclose(coefs[3], truth[3])
        # Only 8-bit rounding separates the fit from the truth.
        for t in _basis.HELD_OUT[regime]:
            assert np.abs(fit.predict(coefs, t) - fit.predict(truth, t)).max() <= 1


def test_compact_rounds_and_dedupes():
    rows, occ = fit.compact(np.array([
        [1, 0, 0, 0, 0, 0],
        [1.000001, -1e-9, 0, 0, 0, 0],
        [0.123456789, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0],
    ]))  # fmt: skip
    assert rows == [[1, 0, 0, 0, 0, 0], [0.12346, 0, 0, 0, 0, 0]]
    assert occ == [0, 0, 1, 0]
    assert "-0.0" not in repr(rows)


def test_predict_rounds_half_to_even_and_clamps():
    half = np.array([[0.5, 0, 0, 0, 0, 0]])
    assert fit.predict(half, ("#850000", "#000000", "#000000"))[0, 0] == 66  # 66.5
    assert fit.predict(half, ("#870000", "#000000", "#000000"))[0, 0] == 68  # 67.5
    assert fit.predict(np.array([[0, 0, 0, 300, -4, 0]]), ("#000000",) * 3).tolist() == [
        [255, 0, 0]
    ]


def test_constant_threshold():
    rows = np.array(
        [[0, 0, 0, 255, 255, 255], [0.001, 0.001, 0.001, 0, 0, 0], [0.004, 0, 0, 0, 0, 0]]
    )
    assert fit.constant(rows).tolist() == [True, True, False]


MASKED = (
    "<svg><defs>"
    '<linearGradient id="lg1"><stop stop-color="#000"/></linearGradient>'
    '<linearGradient id="lg2"><stop stop-color="#fff"/></linearGradient>'
    '<pattern id="p3"><rect fill="url(#lg4)"/><rect fill="#fff"/></pattern>'
    '<linearGradient id="lg4"><stop stop-color="#fff"/></linearGradient>'
    '<linearGradient id="lg5"><stop stop-color="#000"/></linearGradient>'
    '<linearGradient id="lg8" href="#lg9"/>'
    '<linearGradient id="lg9"><stop stop-color="#fff"/></linearGradient>'
    '<mask id="m6"><rect fill="url(#lg1)"/><rect fill="url(#lg2)"/><rect fill="url(#p3)"/>'
    '<rect fill="url(#lg8)"/><circle fill="#fff"/></mask>'
    '<clipPath id="c7"><rect fill="#000"/></clipPath>'
    "</defs>"
    '<g mask="url(#m6)" clip-path="url(#c7)"><rect fill="#123456"/></g>'
    '<rect fill="url(#lg2)"/>'
    "<style>.a{fill:#fff}</style>"
    "</svg>"
)


def test_mask_bound():
    spans = find_colours(MASKED)
    bound = fit.mask_bound(MASKED, [s for s, _, _ in spans])
    assert bound == [
        True,  # lg1: referenced only from the mask
        False,  # lg2: also painted outside it
        True,  # rect in p3, a pattern only the mask uses
        True,  # lg4: only used by p3
        False,  # lg5: unreferenced
        True,  # lg9: only inherited by lg8, which only the mask uses
        True,  # circle in the mask
        True,  # rect in the clipPath
        False,  # masked content itself
        False,  # <style> rules
    ]


def test_slot_rule():
    svg = '<svg><rect fill="#123456"/>\n<mask id="m"><rect fill="#FFFFFF"/><rect fill="#1C1B1A"/></mask></svg>'
    rows = [[0, 0, 0, 18, 52, 86], [0, 0, 0, 255, 255, 255], [1, 0, 0, 0, 0, 0]]
    assert fit.slot_rule(svg, rows, [0, 1, 2]) == [
        "hardcoded #123456 ×1 (line 1): use a token or mix(); constant colours belong only in <mask>/<clipPath>",
        "theme-dependent #1C1B1A ×1 in mask content (line 2): masks take #fff/#000 only",
    ]


def test_collision_needs_per_occurrence_slots(wallpapers):
    regen.install(wallpapers, "collision")
    template = [c for _, _, c in find_colours(common.render("collision", "fireproof"))]
    assert template[1] == template[2]  # two roles, one fireproof hex

    def render(t):
        return common.render("collision", check.theme_spec(t))

    _, entries, errors = fit.fit_aspect(render, "16:9", ["dark", "light"])
    assert errors == [] and entries["16:9/dark"]["n"] == 3

    per_hex = regen.per_hex("collision")
    rows = np.array(per_hex["coefs"])[per_hex["occ"]]
    worst = max(
        np.abs(fit.predict(rows, t) - fit.colours(render(t))).max() for t in _basis.HELD_OUT["dark"]
    )
    assert worst > fit.MAX_ERROR


@pytest.mark.parametrize(
    ("a", "b", "where"), [("abc\ndef", "abc\ndxf", "line 2"), ("abc", "abcd", "line 1")]
)
def test_first_diff(a, b, where):
    assert fit.first_diff(a, b).startswith(f"{where}: ")

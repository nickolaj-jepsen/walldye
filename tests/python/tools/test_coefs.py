import numpy as np
import pytest
from fixtures import pieces

from walldye import ACCENT, BG, FG, MUTED, UI, by_regime, mix
from walldye._design import RenderSpec
from walldye._document import Document
from walldye.tools import coefs, common, themes
from walldye.tools.themes import parse_theme
from walldye.tools.tokenize import find_colors


def test_slot_rows_are_the_formulas():
    parts = ['<svg><rect fill="', '"/><rect fill="', '"/><rect fill="', '"/></svg>']
    colors = [UI, mix(BG, ACCENT, 0.5), by_regime(FG, MUTED)]
    docs = {r: Document(parts, colors, w=1920, h=1080, regime=r) for r in ("dark", "light")}
    _, entries, errors = coefs.serialize_aspect(docs, "16:9")
    assert errors == []
    dark, light = entries["16:9/dark"], entries["16:9/light"]
    assert dark["coefs"] == [
        [0.874, 0.126, 0, 0, 0, 0],
        [0.5, 0, 0.5, 0, 0, 0],
        [0, 1, 0, 0, 0, 0],
    ]
    assert light["coefs"][0] == [0.7984, 0.2016, 0, 0, 0, 0]  # ui's light boost, 0.126 * 1.6
    assert light["coefs"][2] == [0.437, 0.563, 0, 0, 0, 0]  # muted
    assert dark["occ"] == light["occ"] == [0, 1, 2]


def test_compact_rounds_and_dedupes():
    rows, occ = coefs.compact(np.array([
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
    assert coefs.predict(half, ("#850000", "#000000", "#000000"))[0, 0] == 66  # 66.5
    assert coefs.predict(half, ("#870000", "#000000", "#000000"))[0, 0] == 68  # 67.5
    assert coefs.predict(np.array([[0, 0, 0, 300, -4, 0]]), ("#000000",) * 3).tolist() == [
        [255, 0, 0]
    ]


def test_constant_threshold():
    rows = np.array(
        [[0, 0, 0, 255, 255, 255], [0.001, 0.001, 0.001, 0, 0, 0], [0.004, 0, 0, 0, 0, 0]]
    )
    assert coefs.constant(rows).tolist() == [True, True, False]


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
    spans = find_colors(MASKED)
    bound = coefs.mask_bound(MASKED, [s for s, _, _ in spans])
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
    assert coefs.slot_rule(svg, rows, [0, 1, 2]) == [
        "hardcoded #123456 ×1 (line 1): use a token or mix(); constant colors belong only in <mask>/<clipPath>",
        "theme-dependent #1C1B1A ×1 in mask content (line 2): masks take MASK_WHITE, MASK_BLACK and their mixes only",
    ]


def test_collision_needs_per_occurrence_slots(wallpapers):
    pieces.install(wallpapers, "collision")
    template = [c for _, _, c in find_colors(common.render("collision", "fireproof"))]
    assert template[1] == template[2]  # two roles, one fireproof hex
    piece = common.load("collision")
    docs = {
        r: common.draw(piece, RenderSpec("default", piece.params(), "16:9", r))
        for r in ("dark", "light")
    }
    _, entries, errors = coefs.serialize_aspect(docs, "16:9")
    entry = entries["16:9/dark"]
    assert errors == [] and entry["n"] == 3 and entry["occ"][1] != entry["occ"][2]

    # Keyed by hex instead, the second role would take the first one's row.
    rows = np.array(entry["coefs"])[[entry["occ"][0], entry["occ"][1], entry["occ"][1]]]
    worst = max(
        np.abs(coefs.predict(rows, t) - coefs.colors(common.render("collision", t))).max()
        for t in themes.HELD_OUT["dark"]
    )
    assert worst > coefs.MAX_ERROR


def test_serialize_aspect_checks_the_slots_it_serializes():
    """A color baked into the text is a slot the document does not know about."""
    parts = ['<svg viewBox="0 0 1920 1080"><rect fill="', '"/><rect fill="#123456"/></svg>']
    docs = {r: Document(parts, [UI], w=1920, h=1080, regime=r) for r in ("dark", "light")}
    _, entries, errors = coefs.serialize_aspect(docs, "16:9")
    assert entries == {} and len(errors) == 2
    assert errors[0].startswith(
        "16:9 dark: the slots found under fireproof are not the document's, line 1:"
    )


def test_serialize_aspect_shares_or_splits_templates():
    dark = Document(['<svg><rect fill="', '"/></svg>'], [UI], w=1920, h=1080, regime="dark")
    same = Document(['<svg><rect fill="', '"/></svg>'], [UI], w=1920, h=1080, regime="light")
    other = Document(['<svg><path fill="', '"/></svg>'], [UI], w=1920, h=1080, regime="light")
    templates, entries, errors = coefs.serialize_aspect({"dark": dark, "light": same}, "21:9")
    assert errors == [] and list(templates) == ["21x9.svg"]
    assert entries["21:9/light"]["file"] == "21x9.svg"
    templates, entries, _ = coefs.serialize_aspect({"dark": dark, "light": other}, "21:9")
    assert list(templates) == ["21x9.svg", "21x9.light.svg"]
    assert templates["21x9.light.svg"] == other.to_svg(parse_theme("flexoki-light"))
    assert entries["21:9/light"]["file"] == "21x9.light.svg" and entries["21:9/light"]["n"] == 1


@pytest.mark.parametrize(
    ("a", "b", "where"), [("abc\ndef", "abc\ndxf", "line 2"), ("abc", "abcd", "line 1")]
)
def test_first_diff(a, b, where):
    assert coefs.first_diff(a, b).startswith(f"{where}: ")

from pathlib import Path

import pytest
from core_support import load, load_file, spec, themes

from walldye import ACCENT, MASK_WHITE, UI
from walldye._document import Document
from walldye._theme import hex_to_rgb, parse_theme
from walldye.tools.tokenize import find_colours, normalise, skeleton

FIXTURES = ("rings", "veil", "pixels", "branchy")
# Two aspects per design keep the fresh-draw comparison quick: 16:9 and a portrait one.
ASPECTS = ("16:9", "9:19.5", "10:16")


def renders():
    for slug in FIXTURES:
        d = load(slug)
        aspects = [a for a in d.aspects if a in ASPECTS][:2]
        for variant in d.variant_names():
            for aspect in aspects:
                for regime in ("dark", "light"):
                    yield slug, variant, aspect, regime


RENDERS = list(renders())


@pytest.mark.parametrize(("slug", "variant", "aspect", "regime"), RENDERS)
def test_one_document_serialises_like_fresh_draws(slug, variant, aspect, regime):
    d = load(slug)
    doc = d.draw(spec(d, variant, aspect, regime))
    for tokens in themes(regime):
        fresh = load(slug)
        assert doc.to_svg(tokens) == fresh.draw(spec(fresh, variant, aspect, regime)).to_svg(tokens)


ROOT = Path(__file__).parents[3]
REAL = sorted(ROOT.glob("wallpapers/*/design.py")) + sorted(
    ROOT.glob(".claude/skills/walldye/examples/*.py")
)


@pytest.mark.parametrize("path", REAL, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_real_designs_serialise_like_fresh_draws(path):
    """The draw-once check for every piece and skill example: 16:9 in both regimes,
    under the template theme, one held-out theme and one probe."""
    d = load_file(path)
    for regime in ("dark", "light"):
        doc = d.draw(spec(d, "default", "16:9", regime))
        all_themes = themes(regime)
        for tokens in (all_themes[0], all_themes[1], all_themes[-1]):
            fresh = load_file(path)
            want = fresh.draw(spec(fresh, "default", "16:9", regime)).to_svg(tokens)
            assert doc.to_svg(tokens) == want


@pytest.mark.parametrize("slug", FIXTURES)
def test_slots_match_the_tokenizer(slug):
    d = load(slug)
    for regime in ("dark", "light"):
        doc = d.draw(spec(d, "default", "16:9", regime))
        for tokens in themes(regime):
            svg = doc.to_svg(tokens)
            assert doc.hexes(tokens) == [c for _, _, c in find_colours(svg)]
            assert doc.skeleton() == skeleton(svg)
            assert normalise(svg) == svg
        assert len(doc.colours()) == len(doc.hexes(themes(regime)[0]))


@pytest.mark.parametrize("slug", FIXTURES)
def test_coefs_are_the_hexes_before_rounding(slug):
    d = load(slug)
    for regime in ("dark", "light"):
        doc = d.draw(spec(d, "default", "16:9", regime))
        rows = doc.coefs()
        assert len(rows) == len(doc.colours())
        # themes()[0] may be fireproof, whose pinned tokens are not derived.
        for tokens in themes(regime)[1:]:
            bg, fg, accent = (hex_to_rgb(tokens[k]) for k in ("bg", "fg", "accent"))
            for (a, b, c, *d_), h in zip(rows, doc.hexes(tokens), strict=True):
                want = [a * bg[i] + b * fg[i] + c * accent[i] + d_[i] for i in range(3)]
                assert max(abs(x - y) for x, y in zip(hex_to_rgb(h), want)) <= 2


def test_light_documents_share_the_skeleton_unless_geometry_branches():
    for slug, same in (("rings", True), ("veil", True), ("branchy", False)):
        d = load(slug)
        dark, light = (d.draw(spec(d, "default", "16:9", r)) for r in ("dark", "light"))
        assert (dark.skeleton() == light.skeleton()) is same


def test_regime_mismatch():
    d = load("rings")
    doc = d.draw(spec(d, "default", "16:9", "dark"))
    with pytest.raises(ValueError, match="dark document cannot be serialised under a light"):
        doc.to_svg(parse_theme("flexoki-light"))
    with pytest.raises(ValueError):
        doc.hexes(parse_theme("solarized-light"))


def test_document_constructor():
    doc = Document(['<a fill="', '"/>'], [ACCENT], w=10, h=5, regime="dark")
    assert doc.to_svg(parse_theme("fireproof")) == '<a fill="#CF6A4C"/>'
    assert doc.skeleton() == '<a fill="#"/>'
    assert (doc.w, doc.h, doc.regime, doc.pixel_grids) == (10, 5, "dark", ())
    assert Document(["x"], [], w=1, h=1, regime="light").to_svg(parse_theme("flexoki-light")) == "x"
    with pytest.raises(ValueError):
        Document(["a", "b"], [UI, MASK_WHITE], w=1, h=1, regime="dark")
    with pytest.raises(ValueError):
        Document(["a"], [], w=1, h=1, regime="dim")


def test_svg_layout():
    d = load("branchy")
    svg = d.draw(spec(d, "default", "16:9", "dark")).to_svg(parse_theme("fireproof"))
    lines = svg.split("\n")
    assert lines[0] == (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080"'
        ' width="1920" height="1080">'
    )
    assert lines[1] == '<rect x="0" y="0" width="1920" height="1080" fill="#1C1B1A"/>'
    assert lines[-2:] == ["</svg>", ""]
    assert "<defs>" not in svg
    v = load("veil")
    svg = v.draw(spec(v, "default", "9:19.5", "light")).to_svg(parse_theme("flexoki-light"))
    lines = svg.split("\n")
    assert 'viewBox="0 0 1080 2340"' in lines[0]
    assert lines[1].startswith("<defs><clipPath") and lines[1].endswith("</defs>")
    assert lines[2].startswith('<rect x="0" y="0" width="1080" height="2340" fill="')

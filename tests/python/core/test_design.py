import re
from pathlib import Path

import pytest
from core_support import load, spec

from walldye import BG_ALT, MASK_WHITE, UI, Canvas, P, Params, design, knob
from walldye._aspect import SITE_ASPECTS, canvas_size, supports
from walldye._design import Design, RenderSpec
from walldye.tools.themes import parse_theme


class Radar(Params):
    sweep: float = knob(default=60, lo=0, hi=360)
    islands: bool = True


class Other(Params):
    x: int = 1


def noop(s: Canvas) -> None:
    pass


def radar(s: Canvas[Radar]) -> None:
    s.fill(P().circle(s.center, s.params.sweep), UI)


def test_design_attributes():
    d = design(aspects=("16:10", "9:19.5"), variants={"late": Radar(sweep=210)}, bg=BG_ALT)(radar)
    assert isinstance(d, Design)
    assert d.fn is radar and d.params_type is Radar and d.bg is BG_ALT
    assert d.declared_aspects == ("16:10", "9:19.5")
    assert d.aspects == ("16:9", "16:10", "9:19.5")
    assert d.variant_names() == ("default", "late")
    assert d.params() == Radar() and d.params("late") == Radar(sweep=210)
    assert d.source == Path(__file__)
    with pytest.raises(KeyError):
        d.params("early")
    with pytest.raises(TypeError):
        d.variants["x"] = Radar()  # read-only
    plain = design()(noop)
    assert plain.params_type is Params and plain.aspects == ("16:9",)
    assert plain.variant_names() == ("default",)
    assert design(aspects="any")(noop).aspects == SITE_ASPECTS

    def unannotated(s):
        pass

    assert design()(unannotated).params_type is Params


@pytest.mark.parametrize(
    ("kw", "error", "match"),
    [
        ({"aspects": "16:9"}, ValueError, "aspects"),
        ({"aspects": ["16:9"]}, TypeError, "aspects"),
        ({"aspects": ()}, ValueError, "aspects"),
        ({"aspects": ("16:10 ",)}, ValueError, "aspects"),
        ({"aspects": ("16:9", "16:9")}, ValueError, "aspects"),
        ({"aspects": ("4:3",)}, ValueError, "aspects"),
        ({"bg": MASK_WHITE}, TypeError, "bg"),
        ({"bg": "#000000"}, TypeError, "bg"),
    ],
)
def test_decorator_argument_errors(kw, error, match):
    with pytest.raises(error, match=match):
        design(**kw)


@pytest.mark.parametrize(
    ("variants", "error", "match"),
    [
        (
            {f"v{k}": Radar(sweep=k) for k in range(5)},
            ValueError,
            "at most 4",
        ),
        ({"Late": Radar(sweep=1)}, ValueError, "lowercase"),
        ({"open--sea": Radar(sweep=1)}, ValueError, "lowercase"),
        ({"-late": Radar(sweep=1)}, ValueError, "lowercase"),
        ({"late\n": Radar(sweep=1)}, ValueError, "lowercase"),
        ({"x" * 25: Radar(sweep=1)}, ValueError, "24"),
        ({"default": Radar(sweep=1)}, ValueError, "default"),
        ({"late": Other(x=2)}, TypeError, "Other.*Radar"),
        ({"late": Radar()}, ValueError, "equals the default"),
        ({"a": Radar(sweep=1), "b": Radar(sweep=1.0)}, ValueError, "are equal"),
        ([Radar(sweep=1)], TypeError, "mapping"),
    ],
)
def test_variant_errors(variants, error, match):
    with pytest.raises(error, match=match):
        design(variants=variants)(radar)


def test_draw_signature_errors():
    def two(s: Canvas, t: int) -> None:
        pass

    def keyword_only(*, s: Canvas) -> None:
        pass

    def bare(s):
        pass

    def wrong(s: int) -> None:
        pass

    for fn in (two, keyword_only):
        with pytest.raises(TypeError, match="exactly one positional parameter"):
            design()(fn)
    with pytest.raises(TypeError, match=re.escape("Canvas[YourParams]")):
        design(variants={"late": Params(seed=3)})(bare)
    with pytest.raises(TypeError, match="annotate"):
        design()(wrong)
    with pytest.raises(TypeError, match=re.escape("Canvas[Radar]")):
        design(variants={"late": Radar(sweep=1)})(noop)
    assert design(variants={"late": Params(seed=3)})(noop).variants["late"].seed == 3


def test_draw_renders_the_spec():
    d = design(variants={"late": Radar(sweep=210)})(radar)
    doc = d.draw(RenderSpec("late", Radar(sweep=210), "10:16", "light"))
    assert (doc.w, doc.h, doc.regime) == (1080, 1728, "light")
    svg = doc.to_svg(parse_theme("flexoki-light"))
    assert '<rect x="0" y="0" width="1080" height="1728" fill="#FFFCF0"/>' in svg
    assert "A210 210" in svg
    with pytest.raises(TypeError, match="draws Radar, got Other"):
        d.draw(RenderSpec("default", Other(), "16:9", "dark"))
    with pytest.raises(TypeError):
        d.draw(RenderSpec("default", Params(), "16:9", "dark"))
    with pytest.raises(ValueError):
        d.draw(RenderSpec("default", Radar(), "16:9", "dim"))
    with pytest.raises(ValueError):
        d.draw(RenderSpec("default", Radar(), "wide", "dark"))


def test_errors_in_draw_propagate_and_close_the_canvas():
    kept: list[Canvas] = []

    def boom(s: Canvas) -> None:
        kept.append(s)
        raise KeyError("boom")

    d = design()(boom)
    with pytest.raises(KeyError, match="boom"):
        d.draw(RenderSpec("default", Params(), "16:9", "dark"))
    with pytest.raises(RuntimeError, match="the canvas is closed"):
        _ = kept[0].w


def test_fixture_designs_load():
    veil = load("veil")
    assert veil.params_type.__name__ == "Veil"
    assert veil.variant_names() == ("default", "dense", "reseeded")
    assert veil.aspects == ("16:9", "9:19.5")
    doc = veil.draw(spec(veil, "dense", "9:19.5", "dark"))
    assert (doc.w, doc.h) == (1080, 2340)


def test_aspects():
    for aspect, size in {
        "16:9": (1920, 1080),
        "16:10": (1728, 1080),
        "21:9": (2520, 1080),
        "32:9": (3840, 1080),
        "9:19.5": (1080, 2340),
        "10:16": (1080, 1728),
    }.items():
        assert canvas_size(aspect) == size
    assert canvas_size("3440x1440") == (2580, 1080)
    assert canvas_size(0.5) == (1080, 2160)
    for bad in ("wide", "16:0", "-16:9", "16:9:1", 0, float("inf")):
        with pytest.raises(ValueError):
            canvas_size(bad)
    assert supports(("16:10",), "1728x1080") and not supports(("16:10",), "21:9")
    assert supports((), "16:9")

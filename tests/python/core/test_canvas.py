import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from walldye import (
    ACCENT,
    BG,
    MASK_BLACK,
    MASK_WHITE,
    UI,
    Canvas,
    P,
    Params,
    Rect,
    by_regime,
    mix,
)
from walldye._affine import Affine
from walldye._canvas import close
from walldye._document import Builder
from walldye._noise import Noise
from walldye._svg import Ref
from walldye.tools.themes import parse_theme

HERE = Path(__file__).parent
PIXELS = HERE / "designs" / "pixels" / "design.py"
FIREPROOF = parse_theme("fireproof")
LIGHT = parse_theme("flexoki-light")


class Seeded(Params):
    n: int = 1


def canvas(
    params: Params | None = None, w: int = 1920, h: int = 1080, light: bool = False
) -> tuple[Canvas, Builder]:
    doc = Builder(w, h, "light" if light else "dark")
    s = Canvas(params or Params(), w=w, h=h, light=light, doc=doc, source=PIXELS)
    return s, doc


def lines(doc: Builder, light: bool = False) -> list[str]:
    """The element lines after the header (and the defs line, when there is one)."""
    out = doc.finish().to_svg(LIGHT if light else FIREPROOF).splitlines()
    return out[2:-1] if out[1].startswith("<defs>") else out[1:-1]


def defs(doc: Builder) -> str:
    line = doc.finish().to_svg(FIREPROOF).splitlines()[1]
    assert line.startswith("<defs>") and line.endswith("</defs>")
    return line[len("<defs>") : -len("</defs>")]


SQUARE = P().rect(0, 0, 10, 10)


def test_fill_stroke_and_path_goldens():
    s, doc = canvas()
    s.fill(SQUARE, UI, rule="evenodd", opacity=0.5)
    s.stroke(P().M(0, 0).L(5, 5), ACCENT, 1.5, cap="round", join="bevel", dash=(4, 2.5))
    s.stroke(P().M(0, 0).L(5, 5), mix(UI, BG, 0.5), 1, opacity=np.float64(0.25))
    s.path(P().M(1, 1).L(2, 2), fill="none", stroke=UI, stroke_width=2)
    assert lines(doc) == [
        '<path d="M0 0H10V10H0Z" fill="#343331" fill-rule="evenodd" opacity="0.5"/>',
        (
            '<path d="M0 0L5 5" fill="none" stroke="#CF6A4C" stroke-width="1.5"'
            ' stroke-linecap="round" stroke-linejoin="bevel" stroke-dasharray="4 2.5"/>'
        ),
        '<path d="M0 0L5 5" fill="none" stroke="#282726" stroke-width="1" opacity="0.25"/>',
        '<path d="M1 1L2 2" fill="none" stroke="#343331" stroke-width="2"/>',
    ]


def test_attributes_come_in_one_order():
    s, doc = canvas()
    with s.clip() as c:
        c.add(SQUARE)
    with s.mask() as m:
        m.fill(SQUARE, MASK_WHITE)
    s.path(
        SQUARE,
        mask=m.ref,
        clip_path=c.ref,
        transform=Affine(1, 0, 0, 1, 2.345, 3),
        opacity=0.9,
        stroke_opacity=0.8,
        stroke_dashoffset=1,
        stroke_dasharray=[3, 1],
        stroke_linejoin="miter",
        stroke_linecap="square",
        stroke_width=0.5,
        stroke=ACCENT,
        fill_opacity=0.7,
        fill_rule="nonzero",
        fill=UI,
    )
    assert lines(doc) == [
        (
            '<path d="M0 0H10V10H0Z" fill="#343331" fill-rule="nonzero" fill-opacity="0.7"'
            ' stroke="#CF6A4C" stroke-width="0.5" stroke-linecap="square"'
            ' stroke-linejoin="miter" stroke-dasharray="3 1" stroke-dashoffset="1"'
            ' stroke-opacity="0.8" opacity="0.9" transform="matrix(1 0 0 1 2.35 3)"'
            ' clip-path="url(#cp1)" mask="url(#m2)"/>'
        )
    ]


@pytest.mark.parametrize(
    ("style", "error"),
    [
        ({"stroke_widht": 1}, TypeError),
        ({"fill_opacity": True}, TypeError),
        ({"opacity": float("nan")}, ValueError),
        ({"stroke_width": float("inf")}, ValueError),
        ({"stroke_width": ""}, ValueError),
        ({"stroke_width": "2"}, TypeError),
        ({"stroke_width": -1}, ValueError),
        ({"opacity": 1.5}, ValueError),
        ({"stroke_opacity": -0.1}, ValueError),
        ({"stroke_dasharray": []}, ValueError),
        ({"stroke_dasharray": [0, 0]}, ValueError),
        ({"stroke_dasharray": [2, -1]}, ValueError),
        ({"stroke_dasharray": "4 2"}, TypeError),
        ({"stroke_dasharray": [2, True]}, TypeError),
        ({"stroke_linecap": "flat"}, ValueError),
        ({"stroke_linejoin": "sharp"}, ValueError),
        ({"fill_rule": "odd"}, ValueError),
        ({"stroke": "#FF0000"}, TypeError),
        ({"stroke": "red"}, TypeError),
        ({"stroke": MASK_WHITE}, TypeError),
        ({"stroke": None}, TypeError),
        ({"transform": "rotate(3)"}, TypeError),
        ({"clip_path": Ref("m1", "mask")}, TypeError),
        ({"mask": Ref("cp1", "clip")}, TypeError),
        ({"stroke": Ref("cp1", "clip")}, TypeError),
    ],
)
def test_style_validation(style, error):
    s, _ = canvas()
    with pytest.raises(error):
        s.path(SQUARE, fill="none", **style)


def test_paint_validation():
    s, _ = canvas()
    with pytest.raises(TypeError, match="raw color strings are not paints"):
        s.fill(SQUARE, "#FF0000")
    for array in (np.array(["none"]), np.array([]), np.array([1, 2])):
        with pytest.raises(TypeError, match="takes a color, 'none' or a reference"):
            s.fill(SQUARE, array)
    with pytest.raises(TypeError):
        s.fill(SQUARE, MASK_BLACK)
    with pytest.raises(TypeError):
        s.stroke(SQUARE, UI, True)
    with pytest.raises(TypeError):
        s.fill("M0 0", UI)
    with pytest.raises(ValueError):
        s.fill(SQUARE, UI, rule="odd")
    with pytest.raises(TypeError):
        s.group(fill=UI)


def test_empty_paths_draw_nothing():
    s, doc = canvas()
    s.fill(P(), UI)
    s.stroke(P(), UI, 1)
    s.path(P(), fill=UI)
    s.pixel_path(P(), UI, cell=4, origins=[(0, 0)])
    with s.buckets((UI,), "fill"):
        pass
    assert lines(doc) == []
    assert doc.finish().pixel_grids == ()
    with pytest.raises(TypeError):
        s.fill(P(), "#000")  # still validated


def test_groups():
    s, doc = canvas()
    with s.group(opacity=0.5, transform=Affine.translate(3, 4), stroke=UI, stroke_width=2):
        s.fill(SQUARE, ACCENT)
        with s.group():
            s.fill(SQUARE, UI)
    assert lines(doc) == [
        '<g stroke="#343331" stroke-width="2" opacity="0.5" transform="matrix(1 0 0 1 3 4)">',
        '<path d="M0 0H10V10H0Z" fill="#CF6A4C"/>',
        "<g>",
        '<path d="M0 0H10V10H0Z" fill="#343331"/>',
        "</g>",
        "</g>",
    ]


def test_buckets_position_and_order():
    s, doc = canvas()
    s.fill(P().M(0, 0), UI)
    with s.buckets((UI, ACCENT, UI), "fill", opacity=0.5) as b:
        assert len(b) == 3
        b[2].rect(2, 2, 1, 1)
        b[0].rect(0, 0, 1, 1)
        b[np.int64(2)].rect(3, 3, 1, 1)
        s.fill(P().M(5, 5), ACCENT)
    s.fill(P().M(9, 9), UI)
    assert lines(doc) == [
        '<path d="M0 0" fill="#343331"/>',
        '<path d="M0 0H1V1H0Z" fill="#343331" opacity="0.5"/>',
        '<path d="M2 2H3V3H2ZM3 3H4V4H3Z" fill="#343331" opacity="0.5"/>',
        '<path d="M5 5" fill="#CF6A4C"/>',
        '<path d="M9 9" fill="#343331"/>',
    ]
    with pytest.raises(RuntimeError, match="the buckets block is closed"):
        b[0]
    with pytest.raises(RuntimeError, match="the buckets block is closed"):
        len(b)


def test_stroke_buckets():
    s, doc = canvas()
    with s.buckets([UI, ACCENT], "stroke", stroke_width=1.4, stroke_linecap="butt") as b:
        b[1].M(0, 0).L(1, 1)
    assert lines(doc) == [
        '<path d="M0 0L1 1" fill="none" stroke="#CF6A4C" stroke-width="1.4" stroke-linecap="butt"/>'
    ]
    with pytest.raises(ValueError, match="stroke_width"):
        s.buckets([UI], "stroke").__enter__()
    with pytest.raises(TypeError, match="stroke="):
        s.buckets([UI], "stroke", stroke=UI, stroke_width=1).__enter__()
    with pytest.raises(ValueError):
        s.buckets([UI], "outline").__enter__()
    with pytest.raises(TypeError, match="raw color"):
        s.buckets(["#000"], "fill").__enter__()
    with s.buckets([UI], "fill") as b:
        for bad, error in ((1, IndexError), (-1, IndexError), (True, TypeError), (0.5, TypeError)):
            with pytest.raises(error):
                b[bad]


def test_sub_surface_sequencing():
    s, doc = canvas()
    with s.group(opacity=0.5):
        with s.clip() as c:
            c.add(SQUARE, rule="evenodd", transform=Affine.scale(2))
            for draw in (
                lambda: s.fill(SQUARE, UI),
                lambda: s.stroke(SQUARE, UI, 1),
                lambda: s.path(SQUARE, fill=UI),
                lambda: s.group().__enter__(),
                lambda: s.buckets([UI], "fill").__enter__(),
                lambda: s.clip().__enter__(),
                lambda: s.mask().__enter__(),
                lambda: s.pattern(4, 4).__enter__(),
                lambda: s.pixel_path(SQUARE, UI, cell=1, origins=[(0, 0)]),
            ):
                with pytest.raises(RuntimeError, match="close the clip block first"):
                    draw()
            g = s.linear_gradient([(0, UI)], (0, 0), (1, 0))  # allowed: straight to defs
        s.fill(SQUARE, g, opacity=1)
    with pytest.raises(RuntimeError, match="the clip block is closed"):
        c.add(SQUARE)
    assert c.ref == Ref("cp1", "clip") and str(c.ref) == "url(#cp1)"
    assert lines(doc) == [
        '<g opacity="0.5">',
        '<path d="M0 0H10V10H0Z" fill="url(#lg2)" opacity="1"/>',
        "</g>",
    ]
    assert defs(doc) == (
        '<linearGradient id="lg2" x1="0" y1="0" x2="1" y2="0" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#343331"/></linearGradient>'
        '<clipPath id="cp1"><path d="M0 0H10V10H0Z" clip-rule="evenodd"'
        ' transform="matrix(2 0 0 2 0 0)"/></clipPath>'
    )


def test_mask_surface():
    s, doc = canvas()
    canvas_paint = s.linear_gradient([(0, UI)], (0, 0), (1, 0))
    with s.mask() as m:
        gray = mix(MASK_BLACK, MASK_WHITE, 0.4)
        fade = m.radial_gradient([(0, MASK_WHITE), (1, gray, 0.5)], (5, 5), 5, units="bbox")
        with m.group(opacity=0.5, transform=Affine.translate(1, 1)):
            m.fill(SQUARE, fade)
        m.stroke(P().M(0, 0).L(1, 1), MASK_BLACK, 2, cap="round")
        with pytest.raises(TypeError):
            m.fill(SQUARE, UI)
        with pytest.raises(TypeError):
            m.fill(SQUARE, canvas_paint)
        with pytest.raises(TypeError):
            m.linear_gradient([(0, UI)], (0, 0), (1, 1))
    with pytest.raises(RuntimeError, match="the mask block is closed"):
        m.fill(SQUARE, MASK_WHITE)
    assert m.ref.kind == "mask" and fade.kind == "mask_paint"
    with pytest.raises(TypeError):
        s.fill(SQUARE, fade)
    assert defs(doc).endswith(
        '<radialGradient id="rg3" cx="5" cy="5" r="5"><stop offset="0" stop-color="#FFFFFF"/>'
        '<stop offset="1" stop-color="#666666" stop-opacity="0.5"/></radialGradient>'
        '<mask id="m2" maskUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080">'
        '<g opacity="0.5" transform="matrix(1 0 0 1 1 1)">'
        '<path d="M0 0H10V10H0Z" fill="url(#rg3)"/>'
        '</g><path d="M0 0L1 1" fill="none" stroke="#000000" stroke-width="2"'
        ' stroke-linecap="round"/></mask>'
    )


def test_pattern_surface():
    s, doc = canvas()
    with s.pattern(8, 6.5, transform=Affine.rotate(deg=90)) as pat:
        inner = s.linear_gradient([(0, UI), (1, ACCENT)], (0, 0), (8, 0), units="bbox")
        pat.fill(P().circle((4, 4), 2), inner)
        pat.stroke(P().M(0, 0).L(8, 8), by_regime(UI, ACCENT), 1)
        pat.path(P().M(1, 1), fill="none", stroke=UI, stroke_width=1)
        with pat.group(opacity=0.5):
            pat.fill(SQUARE, UI)
        with pytest.raises(TypeError):
            pat.fill(SQUARE, MASK_WHITE)
    s.fill(SQUARE, pat.ref)
    with pytest.raises(RuntimeError, match="the pattern block is closed"):
        pat.fill(SQUARE, UI)
    assert lines(doc) == ['<path d="M0 0H10V10H0Z" fill="url(#p1)"/>']
    assert defs(doc) == (
        '<linearGradient id="lg2" x1="0" y1="0" x2="8" y2="0"><stop offset="0"'
        ' stop-color="#343331"/><stop offset="1" stop-color="#CF6A4C"/></linearGradient>'
        '<pattern id="p1" width="8" height="6.5" patternUnits="userSpaceOnUse"'
        ' patternTransform="matrix(0 1 -1 0 0 0)">'
        '<path d="M6 4A2 2 0 1 1 2 4A2 2 0 1 1 6 4Z" fill="url(#lg2)"/>'
        '<path d="M0 0L8 8" fill="none" stroke="#343331" stroke-width="1"/>'
        '<path d="M1 1" fill="none" stroke="#343331" stroke-width="1"/>'
        '<g opacity="0.5"><path d="M0 0H10V10H0Z" fill="#343331"/></g></pattern>'
    )
    for bad in ((0, 4), (4, -1)):
        with pytest.raises(ValueError):
            s.pattern(*bad).__enter__()


def test_gradients():
    s, doc = canvas()
    ref = s.radial_gradient(
        [(0, UI), (0.5, ACCENT, 0.25), (1, BG)], (100.1234, 50), 40, focus=(90, 45)
    )
    assert ref == Ref("rg1", "paint")
    assert defs(doc) == (
        '<radialGradient id="rg1" cx="100.123" cy="50" r="40" fx="90" fy="45"'
        ' gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#343331"/>'
        '<stop offset="0.5" stop-color="#CF6A4C" stop-opacity="0.25"/>'
        '<stop offset="1" stop-color="#1C1B1A"/></radialGradient>'
    )
    for stops in ([], [(0.5, UI), (0.2, BG)], [(1.2, UI)], [(0, UI, 2)], [(0, "#000")], [(0,)]):
        with pytest.raises((ValueError, TypeError)):
            s.linear_gradient(stops, (0, 0), (1, 1))
    with pytest.raises(ValueError):
        s.linear_gradient([(0, UI)], (0, 0), (1, 1), units="objectBoundingBox")
    with pytest.raises(ValueError):
        s.radial_gradient([(0, UI)], (0, 0), -1)


def test_ids_share_one_counter():
    s, doc = canvas()
    with s.clip() as c:
        pass
    with s.mask() as m:
        pass
    with s.pattern(2, 2) as p:
        pass
    ids = [c.ref.id, m.ref.id, p.ref.id]
    ids += [s.linear_gradient([(0, UI)], (0, 0), (1, 1)).id]
    ids += [s.radial_gradient([(0, UI)], (0, 0), 1).id]
    assert ids == ["cp1", "m2", "p3", "lg4", "rg5"]
    assert defs(doc).startswith('<clipPath id="cp1"></clipPath><mask id="m2"')


def test_pixel_path_records_one_grid_per_origin():
    s, doc = canvas()
    s.pixel_path(P().rect(0, 0, 2, 2), UI, cell=2, origins=[(10, 20), (30.5, 20)], opacity=0.5)
    s.pixel_path(P().rect(0, 0, 3, 3), ACCENT, cell=3, origins=[(0, 0)])
    assert lines(doc) == [
        '<path d="M0 0H2V2H0Z" class="px" fill="#343331" opacity="0.5"/>',
        '<path d="M0 0H3V3H0Z" class="px" fill="#CF6A4C"/>',
    ]
    assert doc.finish().pixel_grids == ((2.0, 10.0, 20.0), (2.0, 30.5, 20.0), (3.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        s.pixel_path(SQUARE, UI, cell=2, origins=[])
    with pytest.raises(ValueError):
        s.pixel_path(SQUARE, UI, cell=0, origins=[(0, 0)])


def test_closed_canvas():
    s, _ = canvas()
    close(s)
    for use in (
        lambda: s.w,
        lambda: s.light,
        lambda: s.params,
        lambda: s.center,
        lambda: s.frac(0, 0),
        lambda: s.rng(1),
        lambda: s.data("rows.json"),
        lambda: s.fill(SQUARE, UI),
        lambda: s.linear_gradient([(0, UI)], (0, 0), (1, 1)),
        lambda: s.clip().__enter__(),
    ):
        with pytest.raises(RuntimeError, match="the canvas is closed"):
            use()


def test_layout():
    s, _ = canvas()
    assert (s.w, s.h, s.landscape, s.light) == (1920, 1080, True, False)
    assert s.center == (960.0, 540.0)
    assert s.frac(0.25, 1) == (480.0, 1080.0)
    assert s.pick(landscape=(0.5, 0.5), portrait=(0.1, 0.1)) == (960.0, 540.0)
    assert s.pick(landscape=(0.25, 500 / 1080), portrait=(0, 0), snap=40) == (480.0, 480.0)
    assert s.pick(landscape=(0.25, 540 / 1080), portrait=(0, 0), snap=40) == (480.0, 560.0)
    assert s.pick(landscape=(0.5, 0.5), portrait=(0, 0), snap=7) == (959.0, 539.0)
    assert s.inset(60) == Rect(60, 60, 1800, 960)
    assert s.inset(-10).contains((-5, -5))
    with pytest.raises(ValueError):
        s.inset(540)
    with pytest.raises(ValueError):
        s.pick(landscape=(0, 0), portrait=(0, 0), snap=0)
    tall, _ = canvas(w=1080, h=2340, light=True)
    assert (tall.landscape, tall.light) == (False, True)
    assert tall.pick(landscape=(0.5, 0.5), portrait=(0.5, 0.25)) == (540.0, 585.0)


def test_data_files():
    s, _ = canvas()
    assert s.data("rows.json") == ["#..#", ".##.", "#..#"]
    assert s.data("names.txt") == "alpha beta gamma\n"
    grid = s.data("grid.npy")
    assert grid.tolist() == [[0, 1, 2], [2, 0, 1]]
    grid[0, 0] = 9  # every call reads the file again
    assert s.data("grid.npy")[0, 0] == 0
    bad_names = ("../design.py", "rows.yaml", ".hidden.json", "sub/rows.json", "", "rows.JSON")
    for bad in (*bad_names, "rows.json\n"):
        with pytest.raises(ValueError):
            s.data(bad)
    with pytest.raises(FileNotFoundError):
        s.data("missing.json")


def draws(s: Canvas) -> dict[str, object]:
    """The first values of each generator family for a few keys."""
    out: dict[str, object] = {}
    for key in (5, "coast", "5"):
        out[f"rng {key!r}"] = [s.rng(key).random() for _ in range(3)]
        out[f"np {key!r}"] = s.np_rng(key).random(3).tolist()
        out[f"noise {key!r}"] = s.noise(key)(0.3, 0.7)
    return out


def test_int_keys_without_a_seed_reproduce_v1_generators():
    s, _ = canvas()
    for k in (0, 5, 2**40, np.int64(7)):
        a, b = s.rng(k), random.Random(int(k))
        assert [a.random() for _ in range(5)] == [b.random() for _ in range(5)]
        assert s.np_rng(k).random(4).tolist() == np.random.default_rng(int(k)).random(4).tolist()
        assert s.noise(k)(1.3, 2.7) == Noise(int(k))(1.3, 2.7)
    r1, r2 = s.rng(3), s.rng(3)
    assert r1 is not r2 and r1.random() == r2.random()


def test_named_streams():
    s, _ = canvas(Seeded(seed=11))
    assert s.rng(5).random() == random.Random("11:5").random()
    assert s.rng("5").random() == random.Random("11:'5'").random()
    digest = hashlib.sha256(b"11:5").digest()[:16]
    want = np.random.default_rng(int.from_bytes(digest, "big")).random(3)
    assert s.np_rng(5).random(3).tolist() == want.tolist()
    assert s.noise(5)(0.5, 0.5) == Noise("11:5")(0.5, 0.5)
    plain, _ = canvas()
    assert plain.rng("coast").random() == random.Random(":'coast'").random()
    assert plain.rng(5).random() != s.rng(5).random()
    # seed 0 is set: it names its streams "0:<key>" and never falls back to the unseeded ones
    zero, _ = canvas(Seeded(seed=0))
    assert zero.rng(5).random() == random.Random("0:5").random() != random.Random(5).random()
    assert zero.rng("k").random() != plain.rng("k").random()
    digest = hashlib.sha256(b"0:5").digest()[:16]
    want = np.random.default_rng(int.from_bytes(digest, "big")).random(3)
    assert zero.np_rng(5).random(3).tolist() == want.tolist()
    assert zero.np_rng("k").random(3).tolist() != plain.np_rng("k").random(3).tolist()
    assert zero.noise(5)(0.5, 0.5) == Noise("0:5")(0.5, 0.5) != Noise(5)(0.5, 0.5)
    assert zero.noise("k")(0.5, 0.5) != plain.noise("k")(0.5, 0.5)
    for bad, error in ((True, TypeError), (-1, ValueError), (1.5, TypeError), (None, TypeError)):
        with pytest.raises(error):
            s.rng(bad)
        with pytest.raises(error):
            s.np_rng(bad)
        with pytest.raises(error):
            s.noise(bad)


STREAM_SCRIPT = """
import json, sys
sys.path.insert(0, {here!r})
from test_canvas import Seeded, canvas, draws
print(json.dumps([draws(canvas()[0]), draws(canvas(Seeded(seed=11))[0])]))
"""


def test_named_streams_are_stable_across_processes():
    here = [draws(canvas()[0]), draws(canvas(Seeded(seed=11))[0])]
    script = STREAM_SCRIPT.format(here=str(HERE))
    for seed in ("0", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True, env=env
        ).stdout
        assert json.loads(out) == here

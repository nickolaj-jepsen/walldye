"""A good design."""

from typing import Literal

import numpy as np

from walldye import (
    ACCENT,
    BG,
    MASK_BLACK,
    MASK_WHITE,
    UI,
    Canvas,
    P,
    Params,
    Style,
    Vec,
    by_regime,
    design,
    knob,
    ladder,
    mix,
    polar,
)


class Radar(Params):
    sweep: float = knob(default=60, lo=0, hi=360, doc="arm bearing", unit="deg")
    steps: int = knob(default=36, lo=8, hi=72)
    islands: bool = True
    mode: Literal["bayer", "bluenoise"] = "bayer"
    level: int = knob(default=3, choices=(1, 3, 5))


VARIANTS = {"dusk": Radar(sweep=210), "open": Radar(islands=False, seed=11)}
THIN: Style = {"stroke": UI, "stroke_width": 1.2}
TONES = ladder((ACCENT, UI), 5)
STRUCT = by_regime(UI, BG)


def helper(s: Canvas) -> None:
    s.fill(P().circle(s.center, 3), UI)


@design(aspects="any", variants=VARIANTS, bg=BG)
def draw(s: Canvas[Radar]) -> None:
    p = s.params
    helper(s)
    c = Vec(s.w * 0.7, s.h * 0.5)
    tip = polar(c, 100 * p.sweep, bearing=p.sweep) + (1, 2)
    arr = np.zeros((3, 2))
    moved = c + arr
    _ = moved.shape
    k = s.np_rng(4).integers(3)
    s.fill(P().circle(c, 10).M(tip).L(k, 2.0), ACCENT, opacity=0.5)
    s.stroke(P().arc(c, 50, deg=(0, 90)), UI, 1.4, cap="round")
    s.path(P().M(1, 2), fill="none", **THIN)
    with s.buckets(TONES, "stroke", stroke_width=1.4, stroke_linecap="butt") as b:
        b[0].M(c)
        b[k].L(c)
    with s.mask() as m:
        m.fill(P().circle(c, 5), mix(MASK_BLACK, MASK_WHITE, 0.5))
    with s.group(mask=m.ref, opacity=0.4):
        s.fill(P().rect(0, 0, 10, 10), TONES.at(0.3))
    with s.clip() as cl:
        cl.add(P().circle(c, 4))
    g = s.linear_gradient([(0, ACCENT), (1, BG, 0.5)], (0, 0), (10, 0))
    s.fill(P().rect(0, 0, 3, 3), g)
    with s.pattern(8, 8) as pat:
        pat.fill(P().circle((4, 4), 2), STRUCT)
    s.fill(P().rect(0, 0, 3, 3), pat.ref)
    r = s.rng(3)
    _ = r.random() + s.noise("coast").fbm(1.0, 2.0) + float(s.noise(2)(np.zeros(3), 1.0).sum())
    _ = s.inset(20).contains(tip)
    _ = s.pick(landscape=(0.5, 0.5), portrait=(0.5, 0.4), snap=8)


@design()
def plain(s: Canvas) -> None:
    s.fill(P().circle((1, 2), 3), BG)

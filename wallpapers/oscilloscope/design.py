"""A Lissajous trace on an oscilloscope graticule, lit more strongly in steps where the beam slows."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    ACCENT_7,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    P,
    Params,
    Vec,
    design,
    knob,
    mix,
    polar,
)
from walldye.field import runs


class Scope(Params):
    fx: int = knob(default=3, lo=1, hi=7, doc="horizontal deflection frequency")
    fy: int = knob(default=2, lo=1, hi=7, doc="vertical deflection frequency")


VARIANTS = {"five-four": Scope(fx=5, fy=4)}

DIV = 60  # graticule division
SW, SH = 10 * DIV, 8 * DIV  # screen
AMP = 3 * DIV  # beam deflection in both axes
PH = math.pi / 2 - 0.12  # horizontal phase lead, just short of quadrature
STRIP, RIM = 150, 26  # control strip width; bezel around the screen
BODY_DX = (STRIP - RIM) / 2  # body centre right of the screen centre
TONES = (ACCENT_3, ACCENT_2, ACCENT_1, ACCENT)  # trace, fast to slow
CUTS = (0.4, 0.7, 0.88)  # slowness thresholds between the tones


def trace(c: Vec, p: Scope, ph: float) -> np.ndarray:
    """One cycle of the beam around screen centre `c` with horizontal phase lead `ph`, as (N, 2)
    points; uniform time steps already crowd them into the slow, tight turns."""
    t = np.linspace(0, 2 * math.pi, 240 * (p.fx + p.fy) + 1)
    return np.column_stack((c.x + AMP * np.sin(p.fx * t + ph), c.y - AMP * np.sin(p.fy * t)))


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Scope]) -> None:
    # landscape: right of centre, leaving the left for windows; portrait: centred, a little low
    c = s.pick(landscape=(0.63, 0.5), portrait=(0.5, 0.56), snap=1) - (BODY_DX, 0)
    x0, y0 = c.x - SW / 2, c.y - SH / 2
    s.path(
        P().rrect(x0 - RIM, y0 - RIM, SW + STRIP + RIM, SH + 2 * RIM, 30),
        fill=mix(BG, BG_ALT, 0.3),
        stroke=BG_ALT,
        stroke_width=2,
    )
    s.path(P().rrect(x0, y0, SW, SH, 14), fill=BG_DEEP, stroke=UI, stroke_width=1.5)

    grid = P()
    for i in range(1, 10):
        grid.M(x0 + i * DIV, y0).V(y0 + SH)
    for j in range(1, 8):
        grid.M(x0, y0 + j * DIV).H(x0 + SW)
    s.stroke(grid, UI, 1.2, dash=(1.5, 4.5))
    ticks = P().M(x0, c.y).H(x0 + SW).M(c.x, y0).V(y0 + SH)
    for k in range(1, 50):
        ticks.M(x0 + k * DIV / 5, c.y - 4).V(c.y + 4)
    for k in range(1, 40):
        ticks.M(c.x - 4, y0 + k * DIV / 5).H(c.x + 4)
    s.stroke(ticks, UI, 1.2)

    # One faint previous sweep, barely offset, reads as phosphor persistence.
    p = s.params
    s.stroke(P().poly(trace(c, p, PH + 0.025)), mix(BG_DEEP, ACCENT_5, 0.45), 1.4)
    xy = trace(c, p, PH)
    s.stroke(P().poly(xy), mix(BG_DEEP, ACCENT_7, 0.8), 5, join="round")
    speed = np.hypot(*np.diff(xy, axis=0).T)
    slow = 1 - (speed - speed.min()) / (speed.max() - speed.min())
    tone = np.searchsorted(CUTS, slow)  # how many cuts each segment is slower than
    with s.buckets(TONES, "stroke", stroke_width=2.4, stroke_linecap="round") as b:
        for i in range(len(TONES)):
            for a, e in runs(tone == i):
                b[i].poly(xy[a : e + 1])

    # Controls on an even rhythm down the strip: three knobs, a divider, three buttons, the LED.
    kx = x0 + SW + STRIP / 2 - 13
    ys = [y0 + 40 + i * (SH - 80) / 4 for i in range(5)]
    knobs = P()
    for y in ys[:3]:
        k = Vec(kx, y)
        knobs.circle(k, 18).M(polar(k, 8 * math.sqrt(2), bearing=45))
        knobs.L(polar(k, 12.5 * math.sqrt(2), bearing=45))
    s.stroke(knobs, UI_ALT, 1.5, cap="round")
    mid = (ys[2] + ys[3]) / 2
    s.stroke(P().M(kx - 26, mid).H(kx + 26), UI, 1.5)
    s.stroke(P().dots([(kx + dx, ys[3]) for dx in (-20, 0, 20)], 5), UI, 1.5)
    s.fill(P().circle((kx, ys[4]), 5), ACCENT)

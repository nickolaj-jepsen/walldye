"""Times-table string art: each nail on a ring is strung to the nail k times its number, and the strings are lit where their envelope folds into a cusp."""

import math
from itertools import pairwise

import numpy as np

from walldye import (
    ACCENT,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    P,
    Params,
    design,
    knob,
    mix,
    polar,
    smoothstep,
)
from walldye.field import gauss


class Table(Params):
    multiplier: int = knob(
        default=2, lo=2, hi=9, doc="nail i is strung to nail multiplier * i (mod the nail count)"
    )


VARIANTS = {"times-three": Table(multiplier=3), "times-four": Table(multiplier=4)}

R, N = 380, 200  # ring radius and nail count
SEG = 8  # px between brightness samples along a string
GLOW = 90  # px falloff of brightness away from a string's tangent point
LV, HV = 12, 6  # brightness and warmth levels
KNEE = 0.6  # brightness level that maps to UI; only strings near the lit cusp may exceed it


def tone(lv: int, hv: int) -> Colour:
    """Brightness level `lv`, from near BG through UI to between UI_ALT and UI_HI, blended
    toward the accent ramp by warmth level `hv`."""
    g = lv / (LV - 1)
    lo, hi = mix(BG, BG_ALT, 0.7), mix(UI_ALT, UI_HI, 0.4)
    cold = mix(lo, UI, g / KNEE) if g < KNEE else mix(UI, hi, (g - KNEE) / (1 - KNEE))
    return mix(cold, mix(mix(BG, ACCENT, 0.18), ACCENT, g), hv / (HV - 1))


TONES = tuple(tone(lv, hv) for lv in range(LV) for hv in range(HV))  # index lv * HV + hv


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Table]) -> None:
    k = s.params.multiplier
    # landscape: right of centre, the cusp facing the empty side; portrait: under the clock
    c = s.pick(landscape=(0.651, 0.5), portrait=(0.5, 0.42))
    # The envelope is an epicycloid with k - 1 cusps on a circle of radius R (k - 1) / (k + 1).
    # An even k puts one opposite nail 0; an odd k turns the ring half a cusp gap so one faces left.
    turn = 0.0 if k % 2 == 0 else -math.pi / (k - 1)
    cusp = polar(c, R * (k - 1) / (k + 1), rad=math.pi)

    s.stroke(P().circle(c, R), BG_ALT, 1.4)
    nails = P()
    for i in range(N):
        a = 2 * math.pi * i / N + turn
        nails.M(polar(c, R + 8, rad=a)).L(polar(c, R + (18 if i % 10 == 0 else 13), rad=a))
    s.stroke(nails, UI, 1.3)

    # Strings through the lit cusp stack into a solid wedge until they fan apart, so there
    # they are drawn thinner, under the rest.
    with (
        s.buckets(TONES, "stroke", stroke_width=0.8) as thin,
        s.buckets(TONES, "stroke", stroke_width=1.1) as thick,
    ):
        for i in range(1, N):
            th = 2 * math.pi * i / N
            a, b = polar(c, R, rad=th + turn), polar(c, R, rad=k * th + turn)
            if abs(b - a) < 1:
                continue
            # where this string touches the envelope
            t = (a * k + b) / (k + 1)
            dc = abs(t - cusp)
            warm = gauss(dc, 150)
            ceil = KNEE + (1 - KNEE) * gauss(dc, 190)
            near = gauss(dc, 14)
            glow = GLOW * (0.55 + 0.45 * smoothstep(0, 70, dc))
            n = max(1, int(abs(b - a) / SEG))
            pts = np.asarray(a) + np.outer(np.arange(n + 1) / n, np.asarray(b - a))
            mid = (pts[:-1] + pts[1:]) / 2
            v = gauss(np.hypot(*(mid - t).T), glow)
            v *= 1 - 0.75 * near * (1 - smoothstep(6, 50, np.hypot(*(mid - cusp).T)))
            lv = np.minimum(LV - 1, (np.minimum(v, ceil) * LV).astype(int))
            # only the lit part of a string warms up, so long strings stay cold across the disc
            hv = np.minimum(HV - 1, (warm * np.minimum(1, v * 2.5) * HV).astype(int))
            key = lv * HV + hv
            fine = (dc < 20) & (hv > 0)
            cut = np.flatnonzero((np.diff(key) != 0) | (np.diff(fine) != 0)) + 1
            for j0, j1 in pairwise((0, *cut, n)):
                (thin if fine[j0] else thick)[key[j0]].poly(pts[[j0, j1]])

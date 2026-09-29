"""Stockinette knit tiled from a two-row pattern cell, with one dropped stitch laddered down its column to a loose loop."""

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_3,
    BG,
    BG_ALT,
    UI,
    Canvas,
    P,
    Path,
    Vec,
    design,
    mix,
    ramp,
    smoothstep,
)
from walldye.geom import spline_points

K = 1.4  # knit scale
SW, SH = 24 * K, 22 * K  # stitch width, row height
RUN = 11  # rows the dropped stitch ran down before its loop came to rest
TONES = (BG_ALT, mix(BG_ALT, UI, 0.14))  # alternate rows, a barely-there nudge
# the loose rungs fade in over four rows, hold, then step to ACCENT_3 over the last three
RUNG_TONES = ramp(BG_ALT, UI, 5)[1:] + ramp(UI, ACCENT_3, 4)[1:]
# the runaway loop in knit units about the top of the row below it: a teardrop whose legs cross
# once; points above that row shift by 0.3 y, leaning the head over to the left
LOOP = np.array(
    [
        (x + 0.3 * min(y, 0), y)
        for x, y in (
            (5, 5),
            (0.5, -5),
            (-9, -14),
            (-13, -29),
            (-6, -43),
            (6, -44),
            (12, -32),
            (8, -16),
            (-0.5, -5),
            (-5, 5),
        )
    ]
)
N = 20  # curve samples per loop segment


def leg(d: Path, a: Vec, b: Vec, bulge: float) -> Path:
    """Append a leaf from `a` to `b` that swells `bulge` each side of the chord."""
    n = (b - a).perp().unit() * bulge
    q1, q3 = a + (b - a) * 0.25, a + (b - a) * 0.75
    return d.M(a).C(q1 + n, q3 + n, b).C(q3 - n, q1 - n, a).Z()


def stitch(d: Path, at: Vec, pull: float = 0.0) -> Path:
    """Append a V stitch hanging from `at` (column center, row top); `pull` shifts the top of
    the V sideways so the stitch leans."""
    for sx in (-1, 1):
        a = at + (pull + sx * 9 * K, -K)
        leg(d, a, at + (0.4 * pull + sx * 1.5 * K, SH + 3 * K), 3.6 * K)
    return d


def cell(c: int, r: int) -> Vec:
    """The top center of the stitch in column `c`, row `r` of the knit."""
    return Vec(c * SW + SW / 2, r * SH)


@design(aspects="any")
def draw(s: Canvas) -> None:
    with s.pattern(SW, 2 * SH) as knit:
        for row, tone in enumerate(TONES):
            d = P()
            for r in (row - 2, row, row + 2):
                stitch(d, Vec(SW / 2, r * SH))
            knit.fill(d, tone)
    s.fill(P().rect(0, 0, s.w, s.h), knit.ref)

    # the ladder hangs in the right third on landscape, a little right of center on portrait,
    # snapped to the knit's columns and rows
    at = s.pick(landscape=(0.726, 0.285), portrait=(0.66, 0.36))
    col, top = round(at.x / SW - 0.5), round(at.y / SH)
    rest = top + RUN
    rows = range(top, rest + 1)

    erase = P()
    for r in rows:
        for c in (col - 1, col, col + 1):
            stitch(erase, cell(c, r))
    s.path(erase, fill=BG, stroke=BG, stroke_width=1.5)

    rnd = s.rng(21)
    gx = col * SW
    with s.buckets(RUNG_TONES, "stroke", stroke_width=3 * K, stroke_linecap="round") as rungs:
        for k in range(RUN - 2):
            y = (top + k) * SH + SH * (0.55 + rnd.uniform(-0.1, 0.1))
            sag = 6 * K * rnd.uniform(0.8, 1.2)
            rung = rungs[min(k, 3) + max(0, k - 5)]
            rung.M(gx - 5 * K, y).Q(gx + SW / 2, y + 2 * sag, gx + SW + 5 * K, y)

    # the flanking columns pull in towards the gap, easing in below the top of the ladder
    with s.buckets(TONES, "fill") as flank:
        for r in rows:
            pull = 2.6 * K * smoothstep(top - 1, top + 3, r)
            stitch(flank[r % 2], cell(col - 1, r), pull)
            stitch(flank[r % 2], cell(col + 1, r), -pull)

    # the loop's second leg crosses over the first: a wide cut along it, then the leg on top
    curve = spline_points(cell(col, rest + 1) + LOOP * (1.2 * K), N)
    s.stroke(P(nd=2).poly(curve[: 7 * N + 1]), ACCENT, 4 * K, cap="round", join="round")
    s.stroke(P(nd=2).poly(curve[7 * N + 9 : 8 * N + 11]), BG, 8 * K)
    s.stroke(P(nd=2).poly(curve[6 * N :]), ACCENT, 4 * K, cap="round", join="round")
    s.fill(stitch(P(), cell(col, rest + 1)), TONES[(rest + 1) % 2])

"""The CS2 AK-47's 30-round spray as a two-figure patent plate: dimensioned bullet holes, and the mouse pull that cancels them."""

import math
from itertools import pairwise

import numpy as np

from walldye import ACCENT, BG_ALT, MUTED, UI, UI_ALT, UI_HI, Canvas, P, Paint, Path, Vec, design
from walldye.pixel import glyphs

O1 = Vec(690, 880)  # Fig. 1: the first shot
F2X = 1260  # Fig. 2: x of the pull's start
CAPTION_Y = 960
# CS2 AK-47 rounds 1-30 as screen (dx, dy) from the first shot: OP.GG aimPunch averages at
# 90 px/deg, round 2-3 jitter zeroed
SPRAY = np.array(
    [
        (0, 0),
        (0, -28),
        (0, -56),
        (3, -118),
        (10, -204),
        (0, -293),
        (-34, -374),
        (-61, -444),
        (-76, -495),
        (-5, -524),
        (106, -515),
        (139, -532),
        (121, -554),
        (176, -551),
        (233, -539),
        (209, -552),
        (109, -566),
        (54, -583),
        (2, -596),
        (-80, -589),
        (-138, -570),
        (-96, -574),
        (-102, -583),
        (-78, -598),
        (-76, -606),
        (-123, -599),
        (-119, -604),
        (-48, -607),
        (60, -588),
        (166, -552),
    ],
    dtype=float,
)
# Fig. 1 leaders: round -> label offset from its hole
LEADERS = {
    1: (60, 0),
    5: (60, 0),
    9: (-60, 0),
    15: (0, 56),
    21: (-60, 0),
    28: (0, -52),
    30: (0, -52),
}
# Fig. 2 ticks: round -> direction of its tick off the pull, and the label offset
PULL_TICKS = {
    10: ((0, 1), (0, 34)),
    15: ((-1, 0), (-38, 0)),
    21: ((1, 0), (38, 0)),
    30: ((0, 1), (0, 34)),
}
TICK = 5  # half-size of a dimension's slash tick
HOLE = 7  # bullet-hole ring radius


def label(s: Canvas, text: str, at: Vec, paint: Paint) -> None:
    """`text` in 5x8 glyphs at twice size, centred on `at` and kept on whole units."""
    glyphs(s, text, paint, at=(round(at.x), round(at.y) - 8), font="5x8", px=2, anchor="middle")


def dimension(dims: Path, ext: Path, a: Vec, b: Vec, feet: tuple[Vec, Vec]) -> None:
    """Dimension line a-b with slash ticks; each end's extension line runs from its foot to 8
    past the dimension line."""
    dims.M(a).L(b)
    for end, foot in zip((a, b), feet):
        dims.M(end + (-TICK, TICK)).L(end + (TICK, -TICK))
        ext.M(foot).L(end + (end - foot).unit() * 8)


@design()
def draw(s: Canvas) -> None:
    shots = [O1 + (dx, dy) for dx, dy in SPRAY.tolist()]

    # the hand is smoother than the averaged holes: two [1,2,1] passes over the sweep, with
    # rounds 1-10 and 30 held
    smooth = SPRAY.copy()
    for _ in range(2):
        smooth[10:29] = (smooth[9:28] + 2 * smooth[10:29] + smooth[11:30]) / 4
    # Fig. 2 is the spray reflected through a point: the pull starts level with the spray's top
    start = Vec(F2X, O1.y + SPRAY[:, 1].min())
    pull = [start - (dx, dy) for dx, dy in smooth.tolist()]

    # registration crosshairs: Fig. 1's first shot and the start of the pull
    marks = P()
    for c in (O1, start):
        marks.M(c + (-54, 0)).H(c.x + 54).M(c + (0, -54)).V(c.y + 54).circle(c, 40)
    s.stroke(marks, BG_ALT, 1)

    # dimensions: the climb to round 10 on the left, the drift across the top
    dims, ext = P(), P()
    top = shots[9]
    dimension(dims, ext, O1 + (-160, 0), Vec(O1.x - 160, top.y), (O1 + (-62, 0), top + (-16, 0)))
    x0, x1 = min(p.x for p in shots), max(p.x for p in shots)
    y0 = min(p.y for p in shots) - 10
    dimension(dims, ext, Vec(x0, 200), Vec(x1, 200), (Vec(x0, y0), Vec(x1, y0)))
    s.stroke(ext, UI, 1)
    s.stroke(dims, UI_ALT, 1.2, cap="round")

    # leaders from the numbered holes to their labels
    leads = P()
    for n, off in LEADERS.items():
        hole, u = shots[n - 1], Vec(*off).unit()
        leads.M(hole + u * 10).L(hole + off - u * 14)
        label(s, str(n), hole + off, UI_HI)
    s.stroke(leads, UI_ALT, 1)

    # firing order through the holes, broken at each ring
    order = P()
    for a, b in pairwise(shots):
        if abs(b - a) > 22:
            u = (b - a).unit()
            order.M(a + u * 10).L(b - u * 10)
    s.stroke(order, UI, 1, dash=(2, 4))

    holes = O1 + SPRAY
    s.stroke(P().dots(holes, HOLE), UI_HI, 1.2)
    s.fill(P().dots(holes, 1), MUTED)

    # Fig. 2: the compensating pull, from a start dot to an arrowhead whose base sits on round 30
    s.stroke(P().spline(pull, tension=0.5), ACCENT, 1.5, cap="round", join="round")
    u = (pull[-1] - pull[-2]).unit()
    head = P().circle(start, 5).arrowhead(pull[-1] + u * 11, 11, rad=math.atan2(u.y, u.x), width=5)
    s.fill(head, ACCENT)

    # correspondence ticks: the same rounds on the pull
    ticks = P()
    for n, (d, off) in PULL_TICKS.items():
        p = pull[n - 1]
        ticks.M(p + Vec(*d) * 12).L(p + Vec(*d) * 22)
        label(s, str(n), p + off, UI_ALT)
    s.stroke(ticks, UI_ALT, 1)

    # link arrow, Fig. 1 to Fig. 2
    link = P().M(930, 560).H(1040).M(1032, 555).L(1040, 560).L(1032, 565)
    s.stroke(link, UI, 1.2, cap="round", join="round")

    label(s, "FIG. 1", Vec(O1.x, CAPTION_Y), UI_ALT)
    label(s, "FIG. 2", Vec(F2X, CAPTION_Y), UI_ALT)

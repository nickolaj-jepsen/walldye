"""A 400 m athletics track in plan, drawn to scale and cropped past one bend: the 200 m staggered starts, and lane 4's race picked out to the finish."""

import math
from itertools import pairwise

from walldye import ACCENT, ACCENT_1, ACCENT_3, UI, UI_ALT, Canvas, P, Vec, design, polar
from walldye.geom import Affine

SC = 10  # px per meter
A = 84.39 / 2 * SC  # half the straight
R0, LANE, N = 36.5, 1.22, 8  # curb radius and lane width (m), lanes
LEG = 4  # the lane picked out
FINISH_INSET = 158  # finish line to the far edge; the bend beyond it runs off the canvas
# Local frame: origin at the track's center, +x along the home straight towards the finish,
# +y towards the home straight; angles in degrees about the start bend, clockwise on screen.
BEND = Vec(-A, 0)
BEND_START, BEND_END = -90, -270  # the bend is run anticlockwise, infield on the left


def run_r(n: int) -> float:
    """Measured running-line radius (m) of lane n: 0.30 m off the curb in lane 1, 0.20 m off the line otherwise."""
    return R0 + (n - 1) * LANE + (0.30 if n == 1 else 0.20)


def start_deg(n: int) -> float:
    """Where lane n's 200 m start sits on the bend: each lane runs the rest of the bend plus the
    straight, so the outer lanes start further round."""
    return BEND_START - math.degrees(math.pi * (run_r(n) - run_r(1)) / run_r(n))


@design(aspects="any")
def draw(s: Canvas) -> None:
    # The finish line sits FINISH_INSET short of the right edge on a landscape screen. On a
    # portrait one the plan turns a quarter clockwise, which keeps the running direction, so
    # the start bend is at the top and the finish near the bottom edge.
    reach = A + FINISH_INSET
    if s.landscape:
        place = Affine.frame((s.w - reach, s.h / 2), deg=0)
    else:
        place = Affine.frame((s.w / 2, s.h - reach), deg=90)
    r_out = (R0 + N * LANE) * SC
    with s.group(transform=place):
        lines = P()
        for k in range(N + 1):
            r = (R0 + k * LANE) * SC
            lines.rrect(-A - r, -r, 2 * (A + r), 2 * r, r)
        s.stroke(lines, UI, 1.5)

        # the staggered starts, then the common finish line across every lane
        marks = P()
        for n in range(1, N + 1):
            a = start_deg(n)
            marks.M(polar(BEND, (R0 + (n - 1) * LANE) * SC, deg=a))
            marks.L(polar(BEND, (R0 + n * LANE) * SC, deg=a))
        marks.M(A, R0 * SC).V(r_out)
        s.stroke(marks, UI_ALT, 2)

        # The race eases in through two darker steps over the first fifth of the bend.
        rc = (R0 + (LEG - 0.5) * LANE) * SC
        a0 = start_deg(LEG)
        cuts = [a0 + f * (BEND_END - a0) for f in (0, 0.1, 0.2)]
        for (a, b), tone in zip(pairwise(cuts), (ACCENT_3, ACCENT_1), strict=True):
            s.stroke(P().arc(BEND, rc, deg=(a, b)), tone, 3)
        s.stroke(P().arc(BEND, rc, deg=(cuts[-1], BEND_END)).H(A), ACCENT, 3)

"""A Smith chart too large for the screen, its grid drawn as exact arcs, with a two-step matching path from a load to the centre."""

import math

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_6,
    BG,
    BG_ALT,
    UI,
    Canvas,
    P,
    Path,
    Vec,
    design,
    mix,
    polar,
)

R = 760  # chart radius
# Least gap between the rim and the far edge: in landscape the open-circuit end sits close to
# the right edge; in portrait the bottom of the rim stays clear of a navigation bar.
EDGE, FOOT = 60, 104
MAJOR = (0.2, 0.5, 1, 2, 5)
MINOR = (0.1, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9, 1.2, 1.4, 1.6, 1.8, 3, 4)
CAP = 5  # minor lines stop where the other coordinate passes this
# The load sits at |Γ| = 0.6, 130 degrees anticlockwise from the real axis. A length of line
# turns it clockwise onto the r = 1 circle at z = 1 + 1.5j, and a series reactance of -1.5
# carries it down that circle to the centre.
MAG, LOAD, X = 0.6, 130, 1.5
MEET = math.degrees(math.atan2(2, X))  # arg Γ at z = 1 + jX
MARK = 11  # load marker radius


def grid(c: Vec, values: tuple[float, ...], cap: float) -> Path:
    """Constant-r circles and constant-x arcs for `values` on the chart centred at `c`, each cut
    where the other coordinate passes `cap`; `math.inf` runs them to the open-circuit point."""
    d = P()
    for v in values:
        # r = v: centre v / (1 + v), radius 1 / (1 + v); x lies 2 atan(x / (1 + v)) from its left end
        rc, rr = c + (R * v / (1 + v), 0), R / (1 + v)
        if math.isinf(cap):
            d.circle(rc, rr)
        else:
            a = 2 * math.atan(cap / (1 + v))
            d.arc(rc, rr, rad=(math.pi - a, math.pi + a))
        # x = ±v: centre (1, ±1 / v), radius 1 / v; r lies 2 atan(v / (1 + r)) from the open end
        a0, a1 = math.pi / 2 + 2 * math.atan(v), math.pi / 2 + 2 * math.atan(v / (1 + cap))
        for sign in (1, -1):
            d.arc(c + (R, -sign * R / v), R / v, rad=(sign * a0, sign * a1))
    return d


@design(aspects="any")
def draw(s: Canvas) -> None:
    # 0.6 along the long side and centred across the short one, pulled back from the far edge
    c = s.pick(landscape=(0.6, 0.5), portrait=(0.5, 0.6))
    if s.landscape:
        c = Vec(min(c.x, s.w - R - EDGE), c.y)
    else:
        c = Vec(c.x, min(c.y, s.h - R - FOOT))

    s.stroke(grid(c, MINOR, CAP), mix(BG, BG_ALT, 0.55), 1)
    s.stroke(grid(c, MAJOR, math.inf), BG_ALT, 1.3)
    s.stroke(P().M(c - (R, 0)).L(c + (R, 0)).circle(c, R), UI, 1.6)

    ticks = P()
    for k in range(360):
        ticks.M(polar(c, R + 10, deg=k)).L(polar(c, R + (22 if k % 10 == 0 else 16), deg=k))
    s.stroke(ticks, BG_ALT, 1.2)

    # Chart angles run anticlockwise and screen angles clockwise, hence the minus signs.
    s.stroke(P().circle(c, MAG * R), ACCENT_6, 1.2)
    s.stroke(P().M(c).L(polar(c, MAG * R - MARK, deg=-LOAD)), ACCENT_6, 1.2)
    s.stroke(P().arc(c, MAG * R, deg=(-LOAD, -MEET)), ACCENT_2, 2.4, dash=(12, 8))
    # on the r = 1 circle, reactance x sits at screen angle 2 atan(x / 2) - pi from its centre
    home = P().arc(c + (R / 2, 0), R / 2, rad=(2 * math.atan(X / 2) - math.pi, -math.pi))
    s.stroke(home, ACCENT, 3.5)
    s.path(P().circle(polar(c, MAG * R, deg=-LOAD), MARK), fill=BG, stroke=ACCENT, stroke_width=3)
    s.fill(P().circle(c, 8), ACCENT)

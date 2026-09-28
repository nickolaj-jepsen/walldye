"""Random-walk bands cut into cells by verticals and crossed diagonals, some hatched, with a sun setting into them in six steps."""

import itertools
import math
from typing import NamedTuple

import numpy as np
from shapely.geometry import Point, Polygon

from walldye import ACCENT, ACCENT_2, UI, UI_ALT, UI_HI, Canvas, P, Vec, clamp, design, lerp
from walldye.geom import hatch

X0, X1, Y0 = 180, 1430, 420  # left and right ends of the bands, and the top band's height
GAPS = (45, 130, 70, 110, 85, 100)  # spacing of the seven band lines, shuffled
HATCH = 6  # hatch pitch, and the least gap between a hatch line and a cut
MAX_COS = math.cos(math.radians(12))  # a diagonal meets a band line at 12 degrees or more
SUN, STEPS = 44, 6  # sun radius; positions along its path, the last one filled
PATH = (
    (0.2, -250),
    (0.72, -14),
)  # path ends: fraction of the band width, offset from the top line (negative is above)


class Cell(NamedTuple):
    """The part of the band under line `band` between the cuts at x = a and x = b."""

    band: int
    a: float
    b: float


@design()
def draw(s: Canvas) -> None:
    r = s.rng(65)
    gaps = list(GAPS)
    r.shuffle(gaps)
    base = Y0 + np.concatenate([[0], np.cumsum(gaps)])
    probe = np.linspace(X0, X1, 300)
    lines: list[tuple[list[float], list[float]]] = []  # break points (xs, ys) of each band line
    for y0 in base:
        # a clamped random walk over 11-15 break points, redrawn until it keeps clear of the
        # line above
        while True:
            n = r.randint(11, 15)
            inner = [lerp(X0 + 80, X1 - 80, (k + r.uniform(0.2, 0.8)) / n) for k in range(n)]
            walk, ys = 0.0, []
            for _ in inner:
                walk = clamp(walk + r.uniform(-14, 14), -20, 20)
                ys.append(y0 + walk)
            # flat open ends: no hooks at the frame
            xs, ys = [X0, *inner, X1], [ys[0], *ys, ys[-1]]
            if not lines or min(np.interp(probe, xs, ys) - np.interp(probe, *lines[-1])) > 26:
                break
        lines.append((xs, ys))

    def at(j: int, x: float) -> Vec:
        """The point of band line `j` at `x`."""
        return Vec(x, float(np.interp(x, *lines[j])))

    def heading(j: int, x: float) -> Vec:
        """The unit direction of band line `j` over the 10 units right of `x`."""
        return (at(j, x + 10) - at(j, x)).unit()

    def diag_ok(j: int, a: float, b: float) -> bool:
        """Both diagonals of the cell between cuts a and b leave the band lines at their corners
        at 12 degrees or more, so none runs nearly along an edge."""
        for top, bot in ((j, j + 1), (j + 1, j)):
            d = (at(bot, b) - at(top, a)).unit()
            if d.dot(heading(top, a)) > MAX_COS or d.dot(heading(bot, b - 10)) > MAX_COS:
                return False
        return True

    def inside(c: Cell) -> Polygon:
        """Cell `c` less a HATCH margin at each cut."""
        lo, hi = c.a + HATCH, c.b - HATCH
        rim = []
        for j in (c.band, c.band + 1):
            xs = [lo, *(x for x in lines[j][0] if lo < x < hi), hi]
            rim.append([at(j, x) for x in xs])
        return Polygon([*rim[0], *reversed(rim[1])])

    edges = P()
    for xs, ys in lines:
        edges.poly(np.column_stack([xs, ys]))
    cuts: list[tuple[Vec, Vec]] = []
    cells: list[Cell] = []
    for j in range(len(lines) - 1):
        drawn = sorted(r.uniform(X0 + 40, X1 - 40) for _ in range(r.randint(5, 9)))
        # drop a cut within 40 of the one drawn before it
        stops = [x for k, x in enumerate(drawn) if k == 0 or x - drawn[k - 1] > 40]
        cuts += [(at(j, x), at(j + 1, x)) for x in stops]
        for a, b in itertools.pairwise(stops):
            if 40 < b - a < 260 and r.random() < 0.4 and diag_ok(j, a, b):
                cuts += [(at(j, a), at(j + 1, b)), (at(j + 1, a), at(j, b))]
            else:
                cells.append(Cell(j, a, b))
    for p, q in cuts:
        edges.M(p).L(q)

    # the picked-out cell: mid-height, of middling width, in the left two thirds
    accent = r.choice(
        [
            c
            for c in cells
            if 1 <= c.band <= 4
            and gaps[c.band] >= 70
            and 50 < c.b - c.a < 200
            and X0 + 150 < c.a < X0 + 900
        ]
    )
    hatched, lit = P(), P()
    for cell in cells:
        a, b = cell.a, cell.b
        near = abs(cell.band - accent.band) <= 1 and a < accent.b + 40 and b > accent.a - 40
        if cell == accent or (b - a < 360 and r.random() < 0.35 and not near):
            for seg in hatch(inside(cell), HATCH, deg=90):
                x, (ya, yb) = seg[0, 0], sorted(seg[:, 1])
                (lit if cell == accent else hatched).M(x, ya + 1.5).L(x, yb - 1.5)
    # the sun drops faster as it nears the bands and sets behind the top line
    (fa, ha), (fb, hb) = PATH
    path = []
    for k in range(STEPS):
        u = k / (STEPS - 1)
        x = lerp(X0, X1, lerp(fa, fb, u))
        path.append(Vec(x, at(0, x).y + lerp(ha, hb, u * u)))
    *trail, sun = path
    sky = Polygon([(X0, 0), *zip(*lines[0], strict=True), (X1, 0)])
    s.fill(P().shape(Point(sun).buffer(SUN, 64).intersection(sky)), ACCENT)
    s.stroke(hatched, UI, 1.2)
    s.stroke(lit, ACCENT_2, 1.5)
    s.stroke(edges, UI_ALT, 1.5, join="round")
    rings = P()
    for q in trail:
        rings.circle(q, SUN)
    s.stroke(rings, UI_HI, 1.5)

"""Cherniak's Ringers: one taut string wound round a block of twelve pegs, the best of 4,000 random tours, over a ring lattice."""

import math

from shapely.geometry import LineString, Point, Polygon

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, Canvas, P, Path, Vec, design, mix, polar
from walldye.geom import Affine

STEP = 70  # lattice pitch; the pegs sit on every fourth lattice point
COLS, ROWS = 4, 3
SIZES = (22, 26, 32, 40, 50, 60, 72)  # peg radii
STRING, GAP = 7, 5  # string width; clearance between the string and a peg
FAR = 650  # lattice rings beyond this (x stretched 1.2) step down a tone

type Peg = tuple[Vec, float]  # centre, radius
type Wrap = tuple[Vec, float]  # centre, signed radius: + turns left round the peg, - right
type Run = tuple[Vec, Vec]


def tangent(a: Wrap, b: Wrap) -> Run:
    """The straight run of a belt from wrap `a` to wrap `b`: its two contact points."""
    (pa, ra), (pb, rb) = a, b
    d = pb - pa
    th = math.atan2(d.y, d.x) + math.acos((ra - rb) / abs(d))
    return polar(pa, ra, rad=th), polar(pb, rb, rad=th)


def wind(
    pegs: list[Peg], order: list[int], sides: list[int]
) -> tuple[list[Wrap], list[Run], list[float]] | None:
    """The wraps, runs and run lengths of a closed string round pegs[order], clockwise; side -1
    wraps a peg from outside, +1 pulls the string in round it. None when two runs come within
    40 units of each other or a run grazes a peg it does not wrap."""
    ring = [(pegs[i][0], s * (pegs[i][1] + GAP + STRING / 2)) for i, s in zip(order, sides)]
    n = len(ring)
    if any(abs(a[0] - b[0]) <= abs(a[1] - b[1]) + 4 for a, b in zip(ring, ring[1:] + ring[:1])):
        return None
    runs = [tangent(ring[k], ring[(k + 1) % n]) for k in range(n)]
    lines = [LineString(r) for r in runs]
    for k, ln in enumerate(lines):
        if any(ln.distance(lines[m]) < 40 for m in range(k + 1, n)):
            return None
        for i, (c, r) in enumerate(pegs):
            wrapped = i in (order[k], order[(k + 1) % n])
            if not wrapped and ln.distance(Point(c)) < r + STRING + 10:
                return None
    return ring, runs, [ln.length for ln in lines]


def string_path(ring: list[Wrap], runs: list[Run], to: Affine) -> Path:
    """The closed string, each wrap's arc then the run that leaves it, mapped by `to`."""
    d = P().M(to(runs[-1][1]))
    for k, (c, rs) in enumerate(ring):
        p_in, p_out = runs[k - 1][1] - c, runs[k][0] - c
        a0, a1 = math.atan2(p_in.y, p_in.x), math.atan2(p_out.y, p_out.x)
        sweep = (a0 - a1) % math.tau if rs > 0 else (a1 - a0) % math.tau
        d.A(abs(rs), abs(rs), 0, sweep > math.pi, rs < 0, to(runs[k][0])).L(to(runs[k][1]))
    return d.Z()


@design(aspects="any")
def draw(s: Canvas) -> None:
    # The block is laid out and wound around its own centre, then placed: left of centre on a
    # landscape screen, turned a quarter so it stands four pegs tall on a portrait one.
    c = s.pick(landscape=(790 / 1920, 560 / 1080), portrait=(0.5, 0.53), snap=10)
    to = Affine.frame(c, deg=0 if s.landscape else 90)
    back = to.inverse()

    r = s.rng(21)
    pegs = [
        (Vec((i - 1.5) * 4 * STEP, (j - 1) * 4 * STEP), float(r.choice(SIZES)))
        for j in range(ROWS)
        for i in range(COLS)
    ]
    heavy = [i for i, (_, rad) in enumerate(pegs) if rad >= 60]

    best: tuple[list[Wrap], list[Run]] | None = None
    best_score = -1.0
    for _ in range(4000):
        order = r.sample(range(len(pegs)), r.randint(8, 10))
        mid = sum((pegs[i][0] for i in order), Vec(0, 0)) / len(order)
        order.sort(key=lambda i: math.atan2(pegs[i][0].y - mid.y, pegs[i][0].x - mid.x))
        sides = [r.choice([-1, -1, 1]) for _ in order]
        if sides.count(1) < 2:
            continue
        got = wind(pegs, order, sides)
        if got is None:
            continue
        ring, runs, lengths = got
        # heavy pegs must take part; idle pegs outside the loop and runs over 40% of it cost
        outline = Polygon([p for run in runs for p in run])
        idle = [
            i
            for i in range(len(pegs))
            if i not in order and not outline.contains(Point(pegs[i][0]))
        ]
        if any(i in idle for i in heavy):
            continue
        total = sum(lengths)
        score = total - 3 * max(0, max(lengths) - 0.4 * total) - 250 * len(idle)
        if score > best_score:
            best, best_score = (ring, runs), score

    # The ring lattice runs off every edge, stepping down a tone away from the block and
    # leaving a clear margin round each peg.
    near, far = P(), P()
    x0, y0 = c.x % STEP, c.y % STEP
    for x in range(round(x0), s.w, STEP):
        for y in range(round(y0), s.h, STEP):
            q = back((x, y))
            if any(abs(q - pc) < rad + GAP + STRING + 4 for pc, rad in pegs):
                continue
            (far if math.hypot(q.x / 1.2, q.y) > FAR else near).circle((x, y), 2.5)
    s.stroke(near, BG_ALT, 1.2)
    s.stroke(far, mix(BG, BG_ALT, 0.5), 1.2)

    discs = P()
    for pc, rad in pegs:
        discs.circle(to(pc), rad)
    s.path(discs, fill=UI, stroke=UI_ALT, stroke_width=2)
    if best is not None:
        s.stroke(string_path(*best, to), ACCENT, STRING, join="round")

"""A theta maze carved by a recursive backtracker in concentric rings, its one solution traced as a thread from the rim gate to the centre."""

import math
from collections import deque
from itertools import pairwise

from walldye import ACCENT, BG_ALT, UI, UI_HI, Canvas, P, Rng, design, ladder, mix, polar

type Cell = tuple[int, int]  # (ring, index); ring 0 is innermost, -1 the open centre
type Link = frozenset[Cell]

R, R0, RINGS, SEED = 390, 30, 14, 1415  # outer radius, centre radius, rings, maze stream
H = (R - R0) / RINGS  # ring width
GATE = 200  # deg: the entrance on the rim
LEAD = 44  # how far the thread trails outside the rim
BIAS = 5  # weight of a move along a ring against a move across rings
# Walls fade past this ring, to halfway from UI to BG_ALT at the rim, so the busy outer rings
# stay quiet and the eye settles inward.
FADE_FROM = 7
TONES = ladder((UI, mix(UI, BG_ALT, 0.5)), RINGS - FADE_FROM)


def ring_r(i: int) -> float:
    """The mid radius of ring `i`, or 0 for the open centre (-1)."""
    return R0 + (i + 0.5) * H if i >= 0 else 0.0


def ring_counts() -> tuple[int, ...]:
    """Cells per ring: 8 in ring 0, doubling outward whenever a cell would grow wider than two
    ring widths."""
    counts = [8]
    for i in range(1, RINGS):
        n = counts[-1]
        counts.append(n * 2 if 2 * math.pi * ring_r(i) / n > 2 * H else n)
    return tuple(counts)


COUNTS = ring_counts()
SPAN = tuple(360 / n for n in COUNTS)  # deg per cell, by ring


def wrap(a: float) -> float:
    """`a` degrees wrapped into [-180, 180)."""
    return (a + 180) % 360 - 180


def mid(c: Cell) -> float:
    """The angle through the middle of cell `c`, in degrees."""
    return (c[1] + 0.5) * SPAN[c[0]]


def link(a: Cell, b: Cell) -> Link:
    """The key of the passage between two cells, whichever way it is walked."""
    return frozenset((a, b))


def neighbours(c: Cell) -> list[Cell]:
    """The cells sharing a wall with `c`: both ring neighbours, the one cell inward, then the one
    or two outward. The order is part of the maze's random draw."""
    i, j = c
    n = COUNTS[i]
    out = [(i, (j + 1) % n), (i, (j - 1) % n)]
    if i > 0:
        out.append((i - 1, j // (n // COUNTS[i - 1])))
    if i + 1 < RINGS:
        k = COUNTS[i + 1] // n
        out += [(i + 1, j * k + m) for m in range(k)]
    return out


def maze(rng: Rng) -> tuple[set[Link], list[Cell]]:
    """The passages a recursive backtracker carves from the gate cell, with a move along a ring
    BIAS times as likely as one across, and the shortest route from the gate cell to ring 0."""
    start = (RINGS - 1, int(GATE / 360 * COUNTS[-1]) % COUNTS[-1])
    links: set[Link] = set()
    seen, stack = {start}, [start]
    while stack:
        here = stack[-1]
        opts = [d for d in neighbours(here) if d not in seen]
        if not opts:
            stack.pop()
            continue
        d = rng.choices(opts, [BIAS if o[0] == here[0] else 1 for o in opts])[0]
        links.add(link(here, d))
        seen.add(d)
        stack.append(d)
    prev: dict[Cell, Cell | None] = {start: None}
    queue, goal = deque([start]), start
    while queue:
        goal = queue.popleft()
        if goal[0] == 0:
            break
        for d in neighbours(goal):
            if d not in prev and link(goal, d) in links:
                prev[d] = goal
                queue.append(d)
    route: list[Cell] = []
    at: Cell | None = goal
    while at is not None:
        route.append(at)
        at = prev[at]
    return links, route[::-1]


def thread(route: list[Cell]) -> list[tuple[float, float]]:
    """Waypoints (radius, deg) of a thread along `route` and on into the centre. Neighbouring
    waypoints share a radius (an arc along a ring) or an angle (a straight run across rings);
    a run across several rings keeps one angle while the wall gaps it passes through overlap."""
    steps = list(pairwise([*route, (-1, 0)]))

    def gap(k: int, ref: float) -> tuple[float, float]:
        """The angles through which step `k` crosses between rings, clear of the walls beside
        the gap, unwrapped to the nearest turn of `ref`."""
        p, c = steps[k]
        outer = max(p, c)
        # the last run into the open centre only has to clear ring 0's short radial walls
        margin = 8 / ring_r(0) if c[0] < 0 else 0.55 * H / ring_r(min(p[0], c[0]))
        centre = ref + wrap(mid(outer) - ref)
        w = max(0.0, SPAN[outer[0]] / 2 - math.degrees(margin))
        return centre - w, centre + w

    pos = mid(route[0])
    pts, a = [(ring_r(route[0][0]), pos)], pos
    for k, (p, c) in enumerate(steps):
        if p[0] == c[0]:
            a += SPAN[p[0]] if c[1] == (p[1] + 1) % COUNTS[p[0]] else -SPAN[p[0]]
            continue
        lo, hi = gap(k, a)
        for j in range(k + 1, len(steps)):
            if steps[j][0][0] == steps[j][1][0]:
                break
            lo2, hi2 = gap(j, (lo + hi) / 2)
            if max(lo, lo2) > min(hi, hi2):
                break
            lo, hi = max(lo, lo2), min(hi, hi2)
        port = min(max(pos, lo), hi)
        if abs(port - pos) > 1e-6:
            pts.append((ring_r(p[0]), port))
        # a run across rings that keeps its angle is one straight line
        if len(pts) > 1 and pts[-2][1] == pts[-1][1] == port:
            pts.pop()
        pts.append((ring_r(c[0]), port))
        pos = port
        a = port + wrap(mid(c) - port) if c[0] >= 0 else port
    return pts


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of centre on a landscape screen; on a portrait one a little high and nudged right,
    # to balance the thread trailing out to the left
    c = s.pick(landscape=(17 / 24, 0.5), portrait=(0.53, 0.42))
    links, route = maze(s.rng(SEED))

    with s.buckets(TONES, "stroke", stroke_width=2, stroke_linecap="round") as walls:
        for i, n in enumerate(COUNTS):
            r_in, r_out = R0 + i * H, R0 + (i + 1) * H
            wall = walls[max(0, i - FADE_FROM)]
            for j in range(n):
                a0, a1 = j * SPAN[i], (j + 1) * SPAN[i]
                if i == 0:
                    opening = (i, j) == route[-1]  # the way into the centre
                else:
                    opening = link((i, j), (i - 1, j // (n // COUNTS[i - 1]))) in links
                if not opening:
                    wall.arc(c, r_in, deg=(a0, a1))
                if link((i, j), (i, (j - 1) % n)) not in links:
                    wall.M(polar(c, r_in, deg=a0)).L(polar(c, r_out, deg=a0))

    gate = route[0][1] * SPAN[-1]
    s.stroke(P().arc(c, R, deg=(gate + SPAN[-1], gate + 360)), UI_HI, 2, cap="round")

    pts = thread(route)
    tail = polar(c, R + LEAD, deg=pts[0][1])
    d = P().M(tail)
    for (r0, a0), (r1, a1) in pairwise([(R + LEAD, pts[0][1]), *pts]):
        if r1 == r0:
            d.A(r1, r1, 0, abs(a1 - a0) > 180, a1 > a0, polar(c, r1, deg=a1))
        else:
            d.L(polar(c, r1, deg=a1))
    s.stroke(d, ACCENT, 2.75, cap="round", join="round")
    s.fill(P().circle(c, 9).circle(tail, 6), ACCENT)

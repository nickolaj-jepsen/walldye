"""An invented metro map on an octilinear grid: shared corridors split into parallel lanes, bends are rounded, interchanges are capsules, and one line is picked out."""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from walldye import (
    ACCENT,
    BG,
    BG_ALT,
    BG_DEEP,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    P,
    Path,
    Vec,
    by_regime,
    design,
    mix,
)
from walldye.geom import Affine

G = 60  # grid step
LANE = 14  # spacing of parallel lines sharing a corridor
LW = 8
R = 30  # bend radius
TICK, BAR = 13, 12  # station tick length; half-length of a terminus bar
HUB, HUB_CORE = 20, 14  # interchange capsule width and its hollow

type Node = tuple[int, int]

# (paint, width, grid polyline); order also sets lane order within shared corridors
LINES: tuple[tuple[Colour, float, tuple[Node, ...]], ...] = (
    (UI, LW, ((10, 5), (18, 5), (20, 7), (20, 11), (18, 13), (10, 13), (8, 11), (8, 7), (10, 5))),
    (UI_ALT, LW, ((5, 9), (17, 9), (19, 11), (26, 11))),
    (ACCENT, 10, ((5, 15), (8, 15), (14, 9), (17, 9), (23, 3), (26, 3))),
    (UI, LW, ((14, 2), (14, 16))),
    (UI_ALT, LW, ((6, 3), (8, 3), (10, 5), (18, 5), (21, 2))),
    (UI, LW, ((11, 16), (11, 14), (10, 13), (8, 13), (6, 11), (6, 6))),
    (UI, LW, ((16, 16), (18, 14), (18, 13), (23, 13), (25, 15))),
)
PICKED = 2  # the accent line; its interchanges get the brighter rim
# river bends in grid units; its ends run on past the canvas edges
RIVER = ((3, 12), (5, 10), (9.5, 10), (11.5, 12), (19.5, 12), (21.5, 14), (23.5, 14), (25, 12.5))
MID = Vec(15.5 * G, 9 * G)  # centre of the network's grid box
# a recess below the ground; on paper BG_DEEP is paler than the page, so shade toward the ink
WATER = by_regime(BG_DEEP, mix(BG, BG_ALT, 0.6))


@dataclass
class Step:
    """One grid step of a line: its lane offset at each end, how many lines share the corridor,
    and the corridor's unit normal, which is the same whichever way a line travels it."""

    a: Node
    b: Node
    o0: float
    o1: float
    shared: int
    nrm: Vec

    @property
    def heading(self) -> Node:
        return (self.b[0] - self.a[0], self.b[1] - self.a[1])


# half a step: the grid node it starts at, if any, and its two ends
type Half = tuple[Node | None, Vec, Vec]


def edges(nodes: Sequence[Node]) -> list[tuple[Node, Node]]:
    """Split a grid polyline into unit steps."""
    out: list[tuple[Node, Node]] = []
    for (x0, y0), (x1, y1) in pairwise(nodes):
        n = max(abs(x1 - x0), abs(y1 - y0))
        dx, dy = (x1 - x0) // n, (y1 - y0) // n
        out += [
            ((x0 + k * dx, y0 + k * dy), (x0 + (k + 1) * dx, y0 + (k + 1) * dy)) for k in range(n)
        ]
    return out


def corridor(a: Node, b: Node) -> tuple[tuple[Node, Node], Vec]:
    """The undirected key of a step and its unit normal."""
    if b < a:
        a, b = b, a
    return (a, b), Vec(b[0] - a[0], b[1] - a[1]).perp().unit()


def cross(u: Vec, v: Vec) -> float:
    return u.x * v.y - u.y * v.x


def rounded(pts: Sequence[Vec], r: float) -> Path:
    """A polyline whose corners are cut by quadratic curves starting up to `r` back along each
    leg (at most half of it)."""
    d = P().M(pts[0])
    for p0, p1, p2 in zip(pts, pts[1:], pts[2:]):
        l0, l1 = abs(p0 - p1), abs(p2 - p1)
        a = p1 + (p0 - p1) * min(r, l0 / 2) / l0
        b = p1 + (p2 - p1) * min(r, l1 / 2) / l1
        d.L(a).Q(p1, b)
    return d.L(pts[-1])


def route(
    k: int, nodes: tuple[Node, ...], lanes: dict[tuple[Node, Node], list[int]]
) -> tuple[list[Vec], dict[Node, tuple[Vec, ...]], list[Step]]:
    """Line `k` in pixels: its corner polyline, its lane points at each grid node it passes, and
    its unit steps. `lanes` lists the lines using each corridor, in lane order."""
    closed = nodes[0] == nodes[-1]
    steps: list[Step] = []
    for a, b in edges(nodes):
        key, nrm = corridor(a, b)
        users = lanes[key]
        off = (users.index(k) - (len(users) - 1) / 2) * LANE
        steps.append(Step(a, b, off, off, len(users), nrm))
    # a lane change on a straight happens mid-step on the less shared side, never inside an interchange
    n = len(steps)
    for i in range(n if closed else n - 1):
        s0, s1 = steps[i], steps[(i + 1) % n]
        if s0.heading == s1.heading and s0.o1 != s1.o0:
            if s0.shared < s1.shared:
                s0.o1 = s1.o0
            else:
                s1.o0 = s0.o1

    def px(p: Vec, nrm: Vec, off: float) -> Vec:
        return p * G + nrm * off

    halves: list[Half] = []
    for st in steps:
        a, b = Vec(*st.a), Vec(*st.b)
        m = (a + b) / 2
        halves += [
            (st.a, px(a, st.nrm, st.o0), px(m, st.nrm, st.o0)),
            (None, px(m, st.nrm, st.o1), px(b, st.nrm, st.o1)),
        ]
    poly: list[Vec] = []
    at: dict[Node, tuple[Vec, ...]] = {}
    for (_, a0, b0), (node, a1, b1) in zip(
        halves, halves[1:] + halves[:1] if closed else halves[1:]
    ):
        d0, d1 = b0 - a0, b1 - a1
        c = cross(d0, d1)
        if node is not None:
            at[node] = (b0, a1)
        if abs(c) < 1e-9:
            if abs(a1 - b0) > 0.5:  # lane change on a straight: a 45-degree jog
                j = d0.unit() * (abs(a1 - b0) / 2)
                poly += [b0 - j, a1 + j]
            continue
        poly.append(a0 + d0 * (cross(a1 - a0, d1) / c))
    if closed:  # start mid-segment so every corner gets rounded
        m = (poly[-1] + poly[0]) / 2
        return [m, *poly, m], at, steps
    at[nodes[0]], at[nodes[-1]] = (halves[0][1],), (halves[-1][2],)
    return [halves[0][1], *poly, halves[-1][2]], at, steps


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(31 / 64, 0.5), portrait=(0.5, 0.5), snap=30)
    if s.landscape:
        place = Affine.translate(c.x - MID.x, c.y - MID.y)
    else:  # mirrored across the diagonal, so the river runs down the screen
        place = Affine(0, 1, 1, 0, c.x - MID.y, c.y - MID.x)
    back = place.inverse()
    x0, x1 = back((0, 0)).x - G, back((s.w, s.h)).x + G  # past both canvas edges

    lanes: dict[tuple[Node, Node], list[int]] = {}
    for k, (*_, nodes) in enumerate(LINES):
        for a, b in edges(nodes):
            lanes.setdefault(corridor(a, b)[0], []).append(k)
    routes = [route(k, nodes, lanes) for k, (*_, nodes) in enumerate(LINES)]

    # an interchange wherever lines meet at a node without all running straight through side by side
    meets: dict[Node, dict[int, tuple[Vec, ...]]] = {}
    dirs: dict[Node, dict[int, set[Node]]] = {}
    for k, ((*_, nodes), (_, at, _)) in enumerate(zip(LINES, routes)):
        for node, ps in at.items():
            meets.setdefault(node, {})[k] = ps
        for a, b in edges(nodes):
            dirs.setdefault(a, {}).setdefault(k, set()).add((b[0] - a[0], b[1] - a[1]))
            dirs.setdefault(b, {}).setdefault(k, set()).add((a[0] - b[0], a[1] - b[1]))
    hubs = {
        n: ps
        for n, ps in meets.items()
        if len(ps) > 1 and len({frozenset(v) for v in dirs[n].values()}) > 1
    }

    with s.group(transform=place):
        river = [Vec(x0, RIVER[0][1] * G), *(Vec(x, y) * G for x, y in RIVER)]
        s.stroke(rounded([*river, Vec(x1, RIVER[-1][1] * G)], 40), WATER, 40, join="round")

        rnd = s.rng(4)
        for k, ((paint, width, nodes), (poly, _, steps)) in enumerate(zip(LINES, routes)):
            ends = P()
            if nodes[0] != nodes[-1]:
                for end, nrm in ((poly[0], steps[0].nrm), (poly[-1], steps[-1].nrm)):
                    ends.M(end - nrm * BAR).L(end + nrm * BAR)
            # station ticks mid-step, on the outer side of any corridor, clear of bends, jogs
            # and interchanges
            ticks = P()
            for n, st in enumerate(steps):
                if (
                    st.a in hubs
                    or st.b in hubs
                    or st.o0 != st.o1
                    or n in (0, len(steps) - 1)
                    or rnd.random() < 0.45
                ):
                    continue
                side = 1 if st.o0 > 0 else -1 if st.o0 < 0 else (1 if k % 2 else -1)
                m = (Vec(*st.a) + st.b) / 2 * G + st.nrm * st.o0
                ticks.M(m).L(m + st.nrm * (side * TICK))
            s.stroke(rounded(poly, R), paint, width, cap="round", join="round")
            s.stroke(ends, paint, 5, cap="round")
            s.stroke(ticks, paint, 4)

        # capsules spanning every lane through the node; the accent line's get the brighter rim
        cores = P()
        with s.buckets((UI_HI, MUTED), "stroke", stroke_width=HUB, stroke_linecap="round") as rims:
            for ps in hubs.values():
                pl = [p for v in ps.values() for p in v]
                a, b = max(((p, q) for p in pl for q in pl), key=lambda pq: abs(pq[1] - pq[0]))
                if abs(b - a) <= 0.5:  # one lane: nudge the end so the round caps draw a dot
                    b = a + (0.01, 0)
                rims[1 if PICKED in ps else 0].M(a).L(b)
                cores.M(a).L(b)
        s.stroke(cores, BG, HUB_CORE, cap="round")

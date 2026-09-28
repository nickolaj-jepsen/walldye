"""A Stellaris-style spiral galaxy: Poisson-disk star systems on two winding arms, joined by a pruned Delaunay hyperlane net around an empty core, with one young empire's border."""

import math
from collections import Counter
from itertools import combinations

import numpy as np
import shapely
from scipy.sparse import coo_array
from scipy.sparse.csgraph import connected_components, dijkstra, minimum_spanning_tree
from scipy.spatial import Delaunay, Voronoi
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    ACCENT_8,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Rect,
    Vec,
    clamp,
    design,
)
from walldye.geom import Affine, parts, poisson_disk

# Everything is built around the galaxy's centre at (0, 0); one transform places the disc.
R = 500
CORE = 0.31 * R  # Stellaris spirals leave the core as an impassable void
PITCH = 1.6 * math.pi / math.log(R / CORE)  # each arm winds 0.8 turn from core rim to edge
TILT = 2.2
ARM_W, ARM_SOFT, FLOOR = 1.4, 0.3, 0.09  # arm half-width (rad), edge softness, inter-arm density
SPACING = 20
LANE_MAX, BRIDGE_MAX, EXTRA = 2.2 * SPACING, 3.5 * SPACING, 0.4
EMPIRE_N = 12
EVENT = (310, 20)  # where the young empire settles, on the arm right of the core
# The sampling window the star field was tuned in: the 16:9 canvas as seen from the centre.
FIELD = Rect(-1330, -540, 1920, 1080)
FAR = 5000  # Voronoi guard points, so the outermost systems get bounded cells too


def density(x: float, y: float) -> float:
    """Chance that a candidate system at (x, y) exists: high on the two arms, low between them,
    zero inside the core and beyond the rim."""
    r = math.hypot(x, y)
    if r < CORE or r > R:
        return 0.0
    theta = TILT + PITCH * math.log(r / CORE)
    off = abs((math.atan2(y, x) - theta) % math.pi - math.pi / 2)  # 0 gap centre, pi/2 arm spine
    arm = clamp((off - (math.pi / 2 - ARM_W)) / ARM_SOFT)
    rim = min(1.0, (r - CORE) / 18, (R - r) / 60)
    return (FLOOR + (1 - FLOOR) * arm) * rim


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of centre on a landscape screen, the left free for windows, never nearer the right
    # edge than at 16:9; on a portrait one the disc spans the width above the middle
    c = s.pick(landscape=(1330 / 1920, 0.5), portrait=(0.5, 0.42))
    if s.landscape:
        c = Vec(min(c.x, s.w - 590), c.y)
    r = s.rng(11)
    raw = poisson_disk(FIELD, SPACING, s.rng(11))
    pts = np.array([p for p in raw if r.random() < density(p[0], p[1])])
    n = len(pts)
    rad = np.hypot(pts[:, 0], pts[:, 1])

    # candidate lanes: Delaunay edges that do not cross the core void
    cand: dict[tuple[int, int], float] = {}
    for simplex in Delaunay(pts).simplices:
        for i, j in combinations(sorted(int(v) for v in simplex), 2):
            if math.hypot(*((pts[i] + pts[j]) / 2)) > CORE:
                cand[(i, j)] = math.hypot(*(pts[i] - pts[j]))
    reach = [e for e in cand if cand[e] <= BRIDGE_MAX]

    # spanning tree over short lanes, long bridges only where nothing shorter joins two parts
    net = coo_array(([cand[e] for e in reach], np.array(reach).T), shape=(n, n))
    tree = minimum_spanning_tree(net).tocoo()
    lanes = {(min(i, j), max(i, j)) for i, j in zip(tree.row.tolist(), tree.col.tolist())}
    _, part = connected_components(tree, directed=False)
    main = int(np.bincount(part).argmax())
    # then loops: EXTRA as many lanes again, drawn from the short edges the tree left out
    spare = sorted(
        (e for e in reach if e not in lanes and cand[e] <= LANE_MAX * 0.85), key=lambda e: cand[e]
    )
    lanes |= set(r.sample(spare, int(EXTRA * len(lanes))))

    # a lone system hanging off a long bridge reads as a stray stick: drop it
    deg = Counter(i for e in lanes for i in e)
    lanes = {e for e in lanes if not (cand[e] > LANE_MAX and min(deg[e[0]], deg[e[1]]) == 1)}
    # trim dangling rim spurs so the disc edge stays clean
    for _ in range(3):
        deg = Counter(i for e in lanes for i in e)
        lanes = {e for e in lanes if not any(deg[i] == 1 and rad[i] > 0.86 * R for i in e)}
    lanes = sorted(e for e in lanes if part[e[0]] == main)
    keep = sorted({i for e in lanes for i in e})
    links: dict[int, list[int]] = {i: [] for i in keep}
    for i, j in lanes:
        links[i].append(j)
        links[j].append(i)

    stars = shapely.points(pts[:, 0].tolist(), pts[:, 1].tolist())
    corners = [(-FAR, -FAR), (FAR, -FAR), (-FAR, FAR), (FAR, FAR)]
    vor = Voronoi(np.vstack([pts, corners]))

    def territory(members: list[int]) -> BaseGeometry:
        """The border blob of the systems in `members`: their Voronoi cells capped at a radius,
        rounded, and pulled back from any unowned system it would swallow."""
        cells = [
            shapely.Polygon(vor.vertices[vor.regions[vor.point_region[i]]]).intersection(
                stars[i].buffer(1.6 * SPACING, quad_segs=8)
            )
            for i in members
        ]
        # closing then opening: fills notches and rounds spikes into the game's soft outline
        g = unary_union(cells).buffer(24, quad_segs=12).buffer(-36, quad_segs=12)
        g = g.buffer(12, quad_segs=12)
        others = np.array([i for i in keep if i not in members])
        near = others[shapely.distance(g, stars[others]) < SPACING]
        if len(near) > 0:
            g = g.difference(unary_union(shapely.buffer(stars[near], 0.6 * SPACING, quad_segs=8)))
            g = g.buffer(8, quad_segs=8).buffer(-14, quad_segs=8).buffer(6, quad_segs=8)
        return max(parts(g), key=lambda q: q.area)

    # The empire: 12 systems by lane distance from a capital near EVENT, deep in an arm, with
    # free systems on many sides, compact, and with no foreign system inside its border.
    hubs = [
        i
        for i in keep
        if math.hypot(*(pts[i] - EVENT)) <= 140 and density(pts[i][0], pts[i][1]) >= 0.95
    ]
    weights = [cand[e] for e in lanes]
    lane_net = coo_array((weights, np.array(lanes).T), shape=(n, n))
    hops = dijkstra(lane_net, directed=False, indices=hubs)
    best: tuple[float, int, list[int], BaseGeometry] | None = None
    for hub, row in zip(hubs, hops, strict=True):
        emp = [int(i) for i in np.argsort(row, kind="stable")[:EMPIRE_N]]
        if min(density(pts[i][0], pts[i][1]) for i in emp) < 0.6:
            continue
        q = pts[emp]
        m = q.mean(0)
        spread = float(np.sqrt(((q - m) ** 2).sum(1).mean()))
        poly = territory(emp)
        others = [i for i in keep if i not in emp]
        if shapely.contains_xy(poly, pts[others, 0], pts[others, 1]).any():
            continue
        # unclaimed neighbours on many sides: the sextants holding adjacent free systems
        sides = {
            int((math.atan2(pts[j][1] - m[1], pts[j][0] - m[0]) + math.pi) / (math.pi / 3))
            for i in emp
            for j in links[i]
            if j not in emp
        }
        score = (
            spread
            + 0.8 * math.hypot(*(pts[hub] - m))
            - 12 * len(sides)
            + 0.05 * math.hypot(*(pts[hub] - EVENT))
        )
        if best is None or score < best[0]:
            best = (score, hub, emp, poly)
    assert best is not None
    _, cap, empire, border = best
    owned = set(empire)
    free = [i for i in keep if i not in owned]

    with s.group(transform=Affine.translate(c.x, c.y)):
        # the core glow: faint, and the void stays empty
        glow = s.radial_gradient([(0, UI), (0.6, BG_ALT, 0.7), (1, BG, 0)], (0, 0), CORE * 1.05)
        s.fill(P().circle((0, 0), CORE * 1.05), glow)

        outline = P().shape(border.simplify(0.8))
        s.fill(outline, ACCENT_8)
        wild, home = P(), P()
        for i, j in lanes:
            (home if i in owned and j in owned else wild).M(pts[i]).L(pts[j])
        s.stroke(wild, UI_ALT, 1)
        s.stroke(home, ACCENT_5, 1)
        s.stroke(outline, ACCENT, 1.5, join="round")

        # a handful of special systems (pulsars, collapsed stars) get a thin ring, like their
        # larger map icons
        special: list[int] = []
        for i in r.sample(free, len(free)):
            if len(special) < 7 and all(math.hypot(*(pts[i] - pts[j])) > 180 for j in special):
                special.append(i)
        s.fill(P().dots(pts[free], 2.2), UI_HI)
        rings = P()
        for i in sorted(special):
            rings.circle(pts[i], 5.5)
        s.stroke(rings, UI_HI, 1)

        s.fill(P().dots(pts[empire[1:]], 2.2), ACCENT_4)
        s.stroke(P().circle(pts[cap], 9), ACCENT_3, 1)
        s.fill(P().circle(pts[cap], 4), ACCENT)

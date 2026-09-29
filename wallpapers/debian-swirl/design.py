"""The Debian swirl as a construction drawing: ten compass arcs, each run on into its full circle, with the tail picked out."""

from itertools import pairwise

from shapely import LineString, Point, Polygon, make_valid
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, Canvas, P, Params, Vec, design, knob, polar
from walldye.geom import Affine, bezier_points, parts

S = 5.4  # canvas units per point of the official artwork
FADE = 640  # construction lines dissolve into the background by this radius
DASHDOT = (24, 6, 3, 6)
ARROW, ARROW_W = 13, 4.2
GAP = 4  # the seam between two arcs of the swirl
TICK = 5  # half the cross marking a center
LIT = 9  # the arc picked out: the tail
OUTER = 5  # the first join whose seam runs on outwards; the ones before face the curl
# The swirl's center line as tangent arcs, fitted to the official openlogo-nd.svg: every arc
# after the first turns 60 degrees, and the radii are whole points, so the centers are the
# corners of a polygon whose sides turn 60 degrees.
TIP = Vec(61.3, 35.87)  # the inner end, in points
TIP_DEG = -43.7  # its direction from the first center
SWEEPS = (32.9, 60, 60, 60, 60, 60, 60, 60, 60, 60)
RADII = (15, 15, 18, 20, 23, 32, 32, 41, 50, 60)


def chain() -> list[tuple[Vec, float, float]]:
    """Each arc's center, radius and starting direction (degrees from the center), in points,
    from the inner end outwards; each arc runs `SWEEPS[k]` degrees anticlockwise from there."""
    out: list[tuple[Vec, float, float]] = []
    p, deg = TIP, TIP_DEG
    for sweep, r in zip(SWEEPS, RADII, strict=True):
        c = p - polar((0, 0), r, deg=deg)
        out.append((c, r, deg))
        deg -= sweep
        p = polar(c, r, deg=deg)
    return out


ARCS = chain()
BOX = (0.536, 0.0, 87.043, 108.449)  # the artwork's bounds, in points


def outline(ctrl: list[float], m: Affine) -> BaseGeometry:
    """One path of the artwork, a start point then cubic segments, as a valid shapely area."""
    pts = [(ctrl[0], ctrl[1])]
    for i in range(2, len(ctrl), 6):
        seg = [pts[-1], ctrl[i : i + 2], ctrl[i + 2 : i + 4], ctrl[i + 4 : i + 6]]
        pts.extend(map(tuple, bezier_points(seg, 16)[1:].tolist()))
    return make_valid(Polygon(m.apply(pts)))


def sector(c: Vec, r0: float, r1: float, a0: float, a1: float) -> Polygon:
    """The annular sector around `c` between radii r0 and r1, from a0 to a1 degrees."""
    n = max(8, int(abs(a1 - a0) / 2))
    angs = [a0 + (a1 - a0) * t / n for t in range(n + 1)]
    ring = [polar(c, r1, deg=a) for a in angs] + [polar(c, r0, deg=a) for a in reversed(angs)]
    return Polygon(ring)


def solid(g: BaseGeometry) -> BaseGeometry:
    """The areas of `g` over 12 square units; smaller ones are slivers left by the cuts."""
    return unary_union([q for q in parts(g) if isinstance(q, Polygon) and q.area > 12])


def strands(g: BaseGeometry) -> list[LineString]:
    """The line parts of `g` longer than 2 units; shorter ones are boolean slivers."""
    return [q for q in parts(g) if isinstance(q, LineString) and q.length > 2]


class Drawing(Params):
    dimensions: bool = knob(default=True, doc="the picked-out arc's radius and angle")


@design(aspects="any", variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    c = s.pick(landscape=(0.64, 0.47), portrait=(0.44, 0.42))
    mid = Vec((BOX[0] + BOX[2]) / 2, (BOX[1] + BOX[3]) / 2)
    m = Affine.translate(c.x, c.y) @ Affine.scale(S) @ Affine.translate(-mid.x, -mid.y)
    paths: list[list[float]] = s.data("swirl.json")
    mark = unary_union([outline(p, m) for p in paths])
    arcs = [(m(ac), r * S, deg) for ac, r, deg in ARCS]
    pole = Vec(sum(a[0].x for a in arcs) / len(arcs), sum(a[0].y for a in arcs) / len(arcs))
    # every join as (center, radius, direction): the inner end, the nine joins, the tail
    joins = [arcs[0]] + [(a[0], a[1], b[2]) for a, b in pairwise(arcs)]
    joins.append((arcs[-1][0], arcs[-1][1], arcs[-1][2] - SWEEPS[-1]))

    # the swirl cut into its arcs along the radii where they meet; each arc's sector reaches
    # past the band to take in the flecks beside it, and the end sectors run on past the tips
    seams = unary_union(
        [
            LineString([polar(ac, r - 40, deg=deg), polar(ac, r + 70, deg=deg)])
            for ac, r, deg in joins[1:-1]
        ]
    ).buffer(GAP / 2, cap_style="flat")
    sectors: list[BaseGeometry] = []
    for k, ((ac, r, deg), sweep) in enumerate(zip(arcs, SWEEPS, strict=True)):
        lo = deg - sweep - (40 if k == len(arcs) - 1 else 0)
        hi = deg + (40 if k == 0 else 0)
        sectors.append(sector(ac, r - 40, r + 70, lo, hi))
    segs = [solid(mark.intersection(q).difference(seams)) for q in sectors]
    rest = solid(mark.difference(unary_union(sectors)))

    # construction: every arc run on into its full circle, and the outer seams run on
    # outwards, all fading with distance and kept off the swirl
    ban = mark.buffer(4)
    field = Point(pole.x, pole.y).buffer(FADE, quad_segs=128)
    lc, lr, ldeg = arcs[LIT]
    lines = P()
    drawn: list[tuple[Vec, float]] = [(lc, lr)]  # arcs sharing a center share a circle
    for ac, r, _ in arcs:
        if any(abs(r - r2) < 1 and abs(ac - c2) < 1 for c2, r2 in drawn):
            continue
        drawn.append((ac, r))
        ring = LineString(Point(ac.x, ac.y).buffer(r, quad_segs=96).exterior.coords)
        for q in strands(ring.intersection(field).difference(ban)):
            lines.poly(q.coords)
    for k, (ac, r, deg) in enumerate(joins):
        if k < OUTER or k in (LIT, LIT + 1):
            continue
        ray = LineString([polar(ac, r, deg=deg), polar(ac, 2 * FADE, deg=deg)])
        for q in strands(ray.intersection(field).difference(ban)):
            lines.poly(q.coords)
    fade = s.radial_gradient([(0, BG_ALT), (0.55, BG_ALT), (1, BG)], pole, FADE)
    s.stroke(lines, fade, 1.2)

    # the polygon of centers, each center ticked
    centers = P().poly([a[0] for a in arcs])
    for ac, _, _ in arcs:
        centers.M(ac.x - TICK, ac.y).H(ac.x + TICK).M(ac.x, ac.y - TICK).V(ac.y + TICK)
    s.stroke(centers, UI, 1.2)

    # the picked-out arc: the radii to its ends, and its full circle
    a0, a1 = ldeg - SWEEPS[LIT], ldeg
    cl = P()
    for deg in (a0, a1):
        cl.M(lc).L(polar(lc, lr + 70, deg=deg))
    s.stroke(cl.circle(lc, lr), UI, 1.2, dash=DASHDOT)

    if s.params.dimensions:
        # dimensions: the picked-out arc's radius, to the band's inner edge, and the angle it
        # turns through, outside it
        dl, heads = P(), P()
        amid = (a0 + a1) / 2
        leader = LineString([lc, polar(lc, lr, deg=amid)]).intersection(segs[LIT])
        hits = [Vec(*q) for g in parts(leader) for q in g.coords]
        tip = min(hits, key=lambda q: abs(q - lc))
        dl.M(lc).L(tip)
        heads.arrowhead(tip, ARROW, deg=amid, width=ARROW_W)
        rd = lr + 45
        dl.arc(lc, rd, deg=(a0, a1))
        heads.arrowhead(polar(lc, rd, deg=a1), ARROW, deg=a1 + 90, width=ARROW_W)
        heads.arrowhead(polar(lc, rd, deg=a0), ARROW, deg=a0 - 90, width=ARROW_W)
        s.stroke(dl, UI_ALT, 1.2)
        s.fill(heads, UI_ALT)

    # the picked-out arc carries the accent; the rest alternate UI and UI_ALT
    with s.buckets((ACCENT, UI, UI_ALT), "fill") as b:
        for k, g in enumerate(segs):
            b[0 if k == LIT else 1 + k % 2].shape(g)
        b[1].shape(rest)

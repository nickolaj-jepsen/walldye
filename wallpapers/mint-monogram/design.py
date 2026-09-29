"""The Linux Mint monogram as a construction drawing: strokes of one width on a half-stroke grid, their edges run on as fading guide lines, the l picked out."""

from shapely import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, ACCENT_3, BG, BG_ALT, UI, UI_ALT, Canvas, P, Vec, design, polar
from walldye.geom import parts

H = 26  # half the stroke width, the grid unit
FADE = 620  # construction lines dissolve into the background by this radius
DASHDOT = (24, 6, 3, 6)
ARROW, ARROW_W = 13, 4.2
# The official badge on the half-stroke grid, origin at the top of the l's outer edge. The mark
# is 14 by 13; its ring runs on a circle 11.8 from the middle of that box.
SIZE = Vec(14, 13)
RING = 11.8
UPRIGHT = (0, 0, 2, 9)  # the l, down to where its corner begins
RUNS = ((4, 11, 10, 13), (12, 4, 14, 9), (8, 4, 10, 9), (4, 4, 6, 9))
# arcs as (center, inner radius, outer radius, from, to) in degrees, clockwise from east
ARCS = (
    (Vec(4, 9), 2, 4, 90, 180),
    (Vec(10, 9), 2, 4, 0, 90),
    (Vec(11, 4), 1, 3, 180, 360),
    (Vec(7, 4), 1, 3, 180, 360),
)
# the grid lines that straight edges lie on, plus y = 4, where the arches meet their legs
EDGES_X = (0, 2, 4, 6, 8, 10, 12, 14)
EDGES_Y = (0, 4, 9, 11, 13)


def band(c: Vec, r0: float, r1: float, a0: float, a1: float) -> Polygon:
    """An annular sector as a polygon, 64 steps per quarter turn."""
    n = max(2, round(64 * (a1 - a0) / 90))
    outer = [polar(c, r1, deg=a0 + (a1 - a0) * k / n) for k in range(n + 1)]
    inner = [polar(c, r0, deg=a1 - (a1 - a0) * k / n) for k in range(n + 1)]
    return Polygon(outer + inner)


def strands(g: BaseGeometry) -> list[LineString]:
    """The line parts of `g` longer than 2 units; shorter ones are boolean slivers."""
    return [q for q in parts(g) if isinstance(q, LineString) and q.length > 2]


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(31 / 48, 0.5), portrait=(0.5, 0.42))
    o = c - SIZE * (H / 2)

    def at(x: float, y: float) -> Vec:
        return o + Vec(x, y) * H

    def rect(r: tuple[float, float, float, float]) -> Polygon:
        return box(*at(r[0], r[1]), *at(r[2], r[3]))

    arcs = [band(at(*a[0]), a[1] * H, a[2] * H, a[3], a[4]) for a in ARCS]
    mark = unary_union([rect(UPRIGHT), *(rect(r) for r in RUNS), *arcs])
    clear = mark.buffer(2.5, join_style="mitre")
    field = Point(c.x, c.y).buffer(FADE, quad_segs=128)
    ring = RING * H

    def outside(g: BaseGeometry) -> list[LineString]:
        """The strands of `g` off the mark, less any that bridge two parts of it (a pocket)."""
        keep = []
        for q in strands(g.difference(clear)):
            ends = [Point(q.coords[0]), Point(q.coords[-1])]
            if not all(e.distance(mark) < 4 for e in ends):
                keep.append(q)
        return keep

    # construction: those lines extended to the fading field
    lines = P()
    for x in EDGES_X:
        a, b = at(x, 0), at(x, 13)
        for q in outside(
            LineString([(a.x, a.y - 2 * FADE), (b.x, b.y + 2 * FADE)]).intersection(field)
        ):
            lines.poly(q.coords)
    for y in EDGES_Y:
        a, b = at(0, y), at(14, y)
        for q in outside(
            LineString([(a.x - 2 * FADE, a.y), (b.x + 2 * FADE, b.y)]).intersection(field)
        ):
            lines.poly(q.coords)
    fade = s.radial_gradient([(0, BG_ALT), (ring * 1.2 / FADE, BG_ALT), (1, BG)], c, FADE)
    s.stroke(lines, fade, 1.2)

    # center lines through the middle of the mark, and the ring's circle
    cl = P()
    for q in outside(LineString([(c.x - ring - 60, c.y), (c.x + ring + 60, c.y)])):
        cl.poly(q.coords)
    for q in outside(LineString([(c.x, c.y - ring - 60), (c.x, c.y + ring + 60)])):
        cl.poly(q.coords)
    s.stroke(cl.circle(c, ring), UI, 1.2, dash=DASHDOT)

    # dimensions: the overall width below, one stroke width across the top of the l
    ext, dl, heads = P(), P(), P()
    x0, x1 = at(0, 0).x, at(14, 0).x
    yd = at(0, 13).y + 64
    for x in (x0, x1):
        ext.M(x, at(0, 9).y + 14).V(yd + 12)
    dl.M(x0, yd).H(x1)
    heads.arrowhead((x1, yd), ARROW, deg=0, width=ARROW_W)
    heads.arrowhead((x0, yd), ARROW, deg=180, width=ARROW_W)
    xa, xb, yt = at(0, 0).x, at(2, 0).x, o.y
    yc = yt - 40
    for x in (xa, xb):
        ext.M(x, yt - 12).V(yc - 12)
    dl.M(xa - 34, yc).H(xa).M(xb, yc).H(xb + 34)
    heads.arrowhead((xa, yc), ARROW, deg=0, width=ARROW_W)
    heads.arrowhead((xb, yc), ARROW, deg=180, width=ARROW_W)
    # radii: a leader from the ring onto the outer edge of one arch and one corner, on the line
    # through the arc's center
    for (ctr, _, r1, _, _), deg in ((ARCS[2], -45.0), (ARCS[1], 45.0)):
        a = at(*ctr)
        d = polar(Vec(0, 0), 1, deg=deg)
        b = d.dot(a - c)
        t = -b + (b * b - (abs(a - c) ** 2 - ring * ring)) ** 0.5
        tip = a + d * (r1 * H)
        dl.M(tip + d * 6).L(a + d * (t - 18))
        heads.arrowhead(tip, ARROW, deg=deg + 180, width=ARROW_W)
    s.stroke(ext, UI, 1.2)
    s.stroke(dl, UI_ALT, 1.2)
    s.fill(heads, UI_ALT)

    # the mark: arcs in UI under the straight runs in UI_ALT, the l in ACCENT
    s.fill(P().shape(mark), UI)
    runs = P()
    for r in RUNS:
        runs.rect(*at(r[0], r[1]), *(Vec(r[2] - r[0], r[3] - r[1]) * H))
    s.fill(runs, UI_ALT)
    s.fill(P().rect(*at(0, 0), 2 * H, 9 * H), ACCENT)

    # the stroke's centerline, as the source artwork draws it; ACCENT_3 over the l
    cen = P()
    cen.M(at(1, 9)).A(3 * H, 3 * H, 0, 0, 0, *at(4, 12)).L(at(10, 12))
    cen.A(3 * H, 3 * H, 0, 0, 0, *at(13, 9)).L(at(13, 4))
    cen.A(2 * H, 2 * H, 0, 0, 0, *at(11, 2)).A(2 * H, 2 * H, 0, 0, 0, *at(9, 4)).L(at(9, 9))
    cen.M(at(9, 4)).A(2 * H, 2 * H, 0, 0, 0, *at(7, 2)).A(2 * H, 2 * H, 0, 0, 0, *at(5, 4))
    cen.L(at(5, 9))
    s.stroke(cen, BG, 1.2, dash=DASHDOT)
    s.stroke(P().M(at(1, 0)).L(at(1, 9)), ACCENT_3, 1.2, dash=DASHDOT)

"""The Arch Linux logo as a construction drawing: flanks and arcs snapped to a grid, run on as fading guide lines, the peak picked out."""

import math

from shapely import LineString, Point, Polygon, box
from shapely.affinity import scale
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, unary_union

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, Canvas, P, Vec, design
from walldye.geom import parts

G = 10  # the grid unit; the mark is 48 units wide and 48 tall
FADE = 620  # construction lines dissolve into the background by this radius
DASHDOT = (24, 6, 3, 6)
ARROW, ARROW_W = 13, 4.2
# Grid points, y up from the middle of the base, snapped from the official archlinux-logo SVG
APEX, FOOT = (0, 48), (24, 0)
MID = 18  # height of the circumscribed circle's centre
FLANK_R = (384, 480)  # left and right: both flanks are faintly hollow arcs
BASE_C = (14, -61)  # centre of the left base arc, across the axis; mirrored for the right
CUT_C, CUT_R = (0, 11), (5.5, 9)  # the inner cut, an ellipse: centre and semi-axes
NOTCH_L = ((0, 29), (22, 59), (10, 54))  # tip, then the centres of its upper and lower edges
NOTCH_R = ((12, 13), (-7, -23), (7, -10))  # tip, then the centres of its lower and upper edges


def disc(c: Vec, r: float) -> Polygon:
    return Point(c.x, c.y).buffer(r, quad_segs=256)


def arc_centre(a: Vec, b: Vec, r: float, side: int) -> Vec:
    """Centre of the circle of radius `r` through `a` and `b`, on `side` (1 or -1) of a to b."""
    m, d = (a + b) / 2, b - a
    return m + d.perp().unit() * side * math.sqrt(r * r - abs(d) ** 2 / 4)


def outline(g: BaseGeometry) -> list[Vec]:
    """The vertices of the outer rings of `g`'s polygons."""
    return [Vec(v[0], v[1]) for q in parts(g) if isinstance(q, Polygon) for v in q.exterior.coords]


def corners(g: BaseGeometry) -> list[Point]:
    """The vertices of `g`'s outline where it turns by more than 12 degrees."""
    out = []
    for q in parts(g):
        if not isinstance(q, Polygon):
            continue
        pts = q.exterior.coords[:-1]
        for a, b, c in zip(pts[-1:] + pts[:-1], pts, pts[1:] + pts[:1], strict=True):
            t0 = math.atan2(b[1] - a[1], b[0] - a[0])
            t1 = math.atan2(c[1] - b[1], c[0] - b[0])
            if abs((t1 - t0 + math.pi) % (2 * math.pi) - math.pi) > math.radians(12):
                out.append(Point(b))
    return out


def strands(g: BaseGeometry) -> list[LineString]:
    """The line parts of `g` longer than 2 units; shorter ones are boolean slivers."""
    return [q for q in parts(g) if isinstance(q, LineString) and q.length > 2]


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(31 / 48, 0.5), portrait=(0.5, 0.42))

    def at(x: float, y: float) -> Vec:
        return Vec(c.x + x * G, c.y - (y - MID) * G)

    apex, fl, fr = at(*APEX), at(-FOOT[0], FOOT[1]), at(*FOOT)
    R = abs(apex - c)  # the circumscribed circle, through the apex and both feet

    # the triangle in its square, both flanks hollowed by a long arc
    flanks = [
        (arc_centre(apex, fl, FLANK_R[0] * G, 1), FLANK_R[0] * G),
        (arc_centre(apex, fr, FLANK_R[1] * G, -1), FLANK_R[1] * G),
    ]
    hull = Polygon([apex, fl, fr]).difference(unary_union([disc(*o) for o in flanks]))

    # the base: two arcs, each struck from across the axis, meeting in a pointed arch
    bl, br = at(*BASE_C), at(-BASE_C[0], BASE_C[1])
    rb = abs(fl - bl)
    long_arcs = [*flanks, (bl, rb), (br, rb)]
    under = disc(bl, rb).intersection(disc(br, rb))

    # the inner cut: an ellipse standing on the axis
    e, (ex, ey) = at(*CUT_C), (CUT_R[0] * G, CUT_R[1] * G)
    cut = scale(disc(e, 1), ex, ey, origin=(e.x, e.y))

    # two notches, each a sliver between two arcs through its tip
    notches, notch_arcs = [], []
    for tip, *centres in (NOTCH_L, NOTCH_R):
        t = at(*tip)
        (a, ra), (b, rb_) = [(at(*o), abs(t - at(*o))) for o in centres]
        notch_arcs += [(a, ra), (b, rb_)]
        side = box(0, 0, t.x, s.h) if tip[0] <= 0 else box(t.x, 0, s.w, s.h)
        sliver = disc(a, ra).symmetric_difference(disc(b, rb_)).intersection(side)
        notches.append(sliver.intersection(Point(t.x, t.y).buffer(12 * G)))
    mark = hull.difference(unary_union([under, cut, *notches]))

    # the peak: the left notch's upper arc, run on across the mark
    a0 = at(*NOTCH_L[1])
    peak = mark.intersection(disc(a0, abs(at(*NOTCH_L[0]) - a0)))
    body = mark.difference(peak)

    # construction: each edge's line or circle, run on from the mark's corners into the fading
    # field, the notches' arcs only as far as the circumscribed circle; the inner cut, the
    # notches and the pointed arch under the mark stay clear
    field = Point(c.x, c.y).buffer(FADE, quad_segs=128)
    inner = Point(c.x, c.y).buffer(R, quad_segs=128)
    solid = mark.buffer(2.5, join_style="mitre")
    arch = under.intersection(box(0, 0, s.w, fl.y))
    clear = unary_union([cut, *notches, arch]).intersection(hull).buffer(2)
    ends = corners(mark)
    runs: list[tuple[BaseGeometry, Polygon]] = [
        *[(disc(o, r).exterior, field) for o, r in long_arcs],
        *[(disc(o, r).exterior, inner) for o, r in notch_arcs],
        (LineString([(c.x - 2 * FADE, fl.y), (c.x + 2 * FADE, fl.y)]), field),
    ]
    lines = P()
    for run, bound in runs:
        own = [v.buffer(5) for v in ends if v.distance(run) < 1]  # the corners on this edge
        pieces = run.intersection(bound).difference(solid).difference(clear)
        for q in strands(linemerge(strands(pieces))):  # rejoin the ring at its start point
            if any(q.intersects(v) for v in own):
                lines.poly(q.coords)
    fade = s.radial_gradient([(0, BG_ALT), (R * 1.2 / FADE, BG_ALT), (1, BG)], c, FADE)
    s.stroke(lines, fade, 1.2)

    # the axis, the inner cut's cross axis and the circumscribed circle
    cl = P().M(c.x, apex.y - 60).V(c.y + R + 60).M(e.x - ex - 30, e.y).H(e.x + ex + 30)
    s.stroke(cl.circle(c, R), UI, 1.2, dash=DASHDOT)

    # the peak's arc: its centre, and its radius to where it meets the right flank
    ext, dl, heads = P(), P(), P()
    ext.M(a0.x - 7, a0.y).H(a0.x + 7).M(a0.x, a0.y - 7).V(a0.y + 7)
    end = max(outline(peak), key=lambda v: v.x)
    u = (end - a0).unit()
    dl.M(a0).L(end - u * ARROW)
    heads.arrowhead(end, ARROW, rad=math.atan2(u.y, u.x), width=ARROW_W)

    # dimensions: the overall width below, the inner cut's width above it, the height at left
    yd = c.y + R + 80
    for x in (fl.x, fr.x):
        ext.M(x, fl.y + 14).V(yd + 12)
    dl.M(fl.x, yd).H(fr.x)
    heads.arrowhead((fr.x, yd), ARROW, deg=0, width=ARROW_W)
    heads.arrowhead((fl.x, yd), ARROW, deg=180, width=ARROW_W)
    x0, x1, yw = e.x - ex, e.x + ex, e.y
    yc = yd - 36
    for x in (x0, x1):
        ext.M(x, yw + 12).V(yc + 12)
    dl.M(x0 - 34, yc).H(x0).M(x1, yc).H(x1 + 34)
    heads.arrowhead((x0, yc), ARROW, deg=0, width=ARROW_W)
    heads.arrowhead((x1, yc), ARROW, deg=180, width=ARROW_W)
    xh = fl.x - 80
    ext.M(apex.x - 14, apex.y).H(xh - 12).M(fl.x - 14, fl.y).H(xh - 12)
    dl.M(xh, apex.y).V(fl.y)
    heads.arrowhead((xh, apex.y), ARROW, deg=-90, width=ARROW_W)
    heads.arrowhead((xh, fl.y), ARROW, deg=90, width=ARROW_W)
    s.stroke(ext, UI, 1.2)
    s.stroke(dl, UI_ALT, 1.2)
    s.fill(heads, UI_ALT)

    s.fill(P().shape(body), UI_ALT)
    s.fill(P().shape(peak), ACCENT)

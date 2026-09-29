"""The Ubuntu Circle of Friends as a compass construction: circles snapped to a radial unit, the ring's width stepped outward as a fading grid, one head picked out."""

from shapely import LinearRing, LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, Canvas, P, Vec, design, polar
from walldye.geom import parts

Q = 6  # the unit every radius is a whole number of
# Radii in Q, snapped from the official 2022 artwork: the ring, the orbit of the head centers,
# a head, and the clearance cut round each head.
RING_IN, RING_OUT, ORBIT, HEAD, CLEAR = 27, 36, 30, 11, 16
PITCH = RING_OUT - RING_IN  # the ring's width, stepped outward as the grid
TURN = 63  # the first head's angle (deg, clockwise from east)
R = (ORBIT + HEAD) * Q  # the circumscribed circle, touching the heads
FADE = 560  # construction lines dissolve into the background by this radius
# where the angle and the head's width are dimensioned, clear of the cuts round the heads
DIM = (ORBIT + CLEAR + 4) * Q
DASHDOT = (24, 6, 3, 6)
ARROW, ARROW_W = 13, 4.2


def strands(g: BaseGeometry) -> list[LineString]:
    """The line parts of `g` longer than 2 units; shorter ones are boolean slivers."""
    return [q for q in parts(g) if isinstance(q, LineString) and q.length > 2]


def circle_line(c: Vec, r: float) -> LinearRing:
    """A circle as a closed line, for boolean cuts."""
    return LinearRing(Point(c.x, c.y).buffer(r, quad_segs=128).exterior.coords)


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(31 / 48, 0.5), portrait=(0.5, 0.42))
    axes = [TURN + 120 * k for k in range(3)]
    heads = [polar(c, ORBIT * Q, deg=a) for a in axes]
    band = Point(c.x, c.y).buffer(RING_OUT * Q, quad_segs=128)
    band = band.difference(Point(c.x, c.y).buffer(RING_IN * Q, quad_segs=128))
    cut = unary_union([Point(h.x, h.y).buffer(CLEAR * Q, quad_segs=96) for h in heads])
    arms = list(parts(band.difference(cut)))
    discs = [Point(h.x, h.y).buffer(HEAD * Q, quad_segs=96) for h in heads]
    solid = unary_union([*arms, *discs]).buffer(2.5)
    field = Point(c.x, c.y).buffer(FADE, quad_segs=128)
    pocket = Point(c.x, c.y).buffer(RING_IN * Q - 1, quad_segs=128)

    # dimensions: the 120 degrees between the two upper heads; below, the overall width and
    # the picked-out head's width, arrows outside
    ext, dl, tips = P(), P(), P()
    a0, a1 = axes[1], axes[2]
    dl.arc(c, DIM, deg=(a0, a1))
    tips.arrowhead(polar(c, DIM, deg=a0), ARROW, deg=a0 - 90, width=ARROW_W)
    tips.arrowhead(polar(c, DIM, deg=a1), ARROW, deg=a1 + 90, width=ARROW_W)
    yd = c.y + (RING_OUT + 2.5 * PITCH) * Q  # midway between the first two grid circles
    for x in (c.x - R, c.x + R):
        ext.M(x, c.y + 14).V(yd + 12)
    dl.M(c.x - R, yd).H(c.x + R)
    tips.arrowhead((c.x + R, yd), ARROW, deg=0, width=ARROW_W)
    tips.arrowhead((c.x - R, yd), ARROW, deg=180, width=ARROW_W)
    h = heads[0]
    x0, x1, yc = h.x - HEAD * Q, h.x + HEAD * Q, c.y + DIM
    for x in (x0, x1):
        ext.M(x, h.y + 14).V(yc + 12)
    dl.M(x0 - 34, yc).H(x0).M(x1, yc).H(x1 + 34)
    tips.arrowhead((x0, yc), ARROW, deg=0, width=ARROW_W)
    tips.arrowhead((x1, yc), ARROW, deg=180, width=ARROW_W)
    marks = [LineString([polar(c, DIM, deg=a0 + (a1 - a0) * k / 64) for k in range(65)])]
    marks += [LineString([(c.x - R, yd), (c.x + R, yd)])]
    marks += [LineString([(x0 - 34, yc), (x0, yc)]), LineString([(x1, yc), (x1 + 34, yc)])]
    clear_of_dims = unary_union(marks).buffer(7)

    # construction: the ring's edges run on through the gaps, each clearance closes round its
    # head, the ring's width steps outward, and spokes run out along the heads and the gaps
    runs: list[BaseGeometry] = [circle_line(c, RING_IN * Q), circle_line(c, RING_OUT * Q)]
    runs += [circle_line(h, CLEAR * Q) for h in heads]
    runs += [
        circle_line(c, r * Q)
        for r in range(RING_OUT + 2 * PITCH, FADE // Q, PITCH)
        if r * Q < FADE - 30
    ]
    runs += [LineString([c, polar(c, 2 * FADE, deg=TURN + 60 * k)]) for k in range(6)]
    lines = P()
    for g in runs:
        g = g.intersection(field).difference(solid).difference(pocket)
        for q in strands(g.difference(clear_of_dims)):
            lines.poly(q.coords)
    fade = s.radial_gradient([(0, BG_ALT), (R * 1.15 / FADE, BG_ALT), (1, BG)], c, FADE)
    s.stroke(lines, fade, 1.2)

    # center lines through the heads and the circumscribed circle
    cl = P()
    for a in axes:
        cl.M(polar(c, R + 72, deg=a)).L(polar(c, R + 72, deg=a + 180))
    s.stroke(cl.circle(c, R), UI, 1.2, dash=DASHDOT)
    s.stroke(ext, UI, 1.2)
    s.stroke(dl, UI_ALT, 1.2)
    s.fill(tips, UI_ALT)

    # the arms, then the heads; the first head carries the accent
    arm = P()
    for g in arms:
        arm.shape(g)
    s.fill(arm, UI)
    with s.buckets((ACCENT, UI_ALT), "fill") as b:
        for k, g in enumerate(discs):
            b[0 if k == 0 else 1].shape(g)

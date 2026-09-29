"""The Fedora infinity mark as a construction drawing: arcs and strokes snapped to a grid, edges run on as fading guide lines, the lower loop picked out."""

import math

from shapely import LineString, Point, Polygon, box
from shapely.affinity import affine_transform
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, Canvas, P, Params, Vec, design, knob, polar
from walldye.geom import parts

G = 4.5  # grid unit: an eighth of the stroke, a 48th of the bubble's radius
R = 48 * G
FADE = 620  # construction lines have faded out by this radius
DASHDOT = (24, 6, 3, 6)
ARROW, ARROW_W = 13, 4.2
RADIUS_DEG = 45  # the scored radius runs down-right, clear of the counters

# Grid coordinates from the bubble's center, snapped from the official artwork.
HALF = 4  # half the stroke width
CORNER = 11  # radius of the squared-off quadrant's corner
STEM_X = -1
HOOK, HOOK_R = (10, -13), 11
LOOP, LOOP_R = (-15, 17), 14
BAR_Y, BAR_END = 3, 10  # the crossbar, and its end cap's center
LEG_END = -11  # the hook's leg runs down to here
TAIL_END = -9  # the loop's top stops half a stroke short of the stem
# Straight edges and the tangents at the extremes of each arc, run on as guide lines.
VERTICALS = (-48, -33, -9, -5, 3, 17, 25, 48)
HORIZONTALS = (-48, -28, 7, 35, 48)  # the crossbar's top would crowd the center line


def arc(c: tuple[float, float], r: float, a0: float, a1: float) -> list[tuple[float, float]]:
    """Points on a circle from `a0` to `a1` degrees, clockwise on screen when `a1 > a0`."""
    n = max(2, int(abs(a1 - a0) / 2))
    return [
        (c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)))
        for a in (a0 + (a1 - a0) * k / n for k in range(n + 1))
    ]


def band(c: tuple[float, float], r: float, a0: float, a1: float) -> Polygon:
    """An arc one stroke wide on the circle of radius `r`, its ends cut square to the arc."""
    return Polygon(arc(c, r + HALF, a0, a1) + arc(c, r - HALF, a1, a0))


def bar(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    """A straight stroke one stroke wide along a horizontal or vertical centerline."""
    return box(
        min(x0, x1) - HALF * (y0 != y1),
        min(y0, y1) - HALF * (x0 != x1),
        max(x0, x1) + HALF * (y0 != y1),
        max(y0, y1) + HALF * (x0 != x1),
    )


def cap(x: float, y: float) -> BaseGeometry:
    """A round end cap centered on a stroke's end."""
    return Point(x, y).buffer(HALF, quad_segs=32)


def strands(g: BaseGeometry) -> list[LineString]:
    """The line parts of `g` longer than 2 units; shorter ones are boolean slivers."""
    return [q for q in parts(g) if isinstance(q, LineString) and q.length > 2]


class Drawing(Params):
    dimensions: bool = knob(default=True, doc="the dimensions and the scored radius")


@design(aspects="any", variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    c = s.pick(landscape=(31 / 48, 0.5), portrait=(0.5, 0.42))

    def canvas(g: BaseGeometry) -> BaseGeometry:
        return affine_transform(g, [G, 0, 0, G, c.x, c.y])

    def at(x: float, y: float) -> Vec:
        return Vec(c.x + x * G, c.y + y * G)

    # the bubble: a circle with its lower-left quadrant squared off and the corner rounded
    k = 48 - CORNER
    bubble = canvas(
        unary_union(
            [
                Point(0, 0).buffer(48, quad_segs=128),
                box(-48, 0, -k, k),
                box(-k, 0, 0, 48),
                Point(-k, k).buffer(CORNER, quad_segs=32),
            ]
        )
    )
    hx, hy = HOOK
    lx, ly = LOOP
    f = unary_union(
        [
            band(HOOK, HOOK_R, -180, 0),
            bar(hx + HOOK_R, hy, hx + HOOK_R, LEG_END),
            cap(hx + HOOK_R, LEG_END),
            bar(STEM_X, hy, STEM_X, ly),
            bar(STEM_X, BAR_Y, BAR_END, BAR_Y),
            cap(BAR_END, BAR_Y),
        ]
    )
    loop = unary_union([band(LOOP, LOOP_R, 0, 270), bar(lx, BAR_Y, TAIL_END, BAR_Y)])
    f, loop = canvas(f), canvas(loop)

    # construction: edges and extreme tangents run on across a fading field, clear of the mark
    field = Point(c.x, c.y).buffer(FADE, quad_segs=128)
    keepout = bubble.buffer(3)
    lines = P()
    for x in VERTICALS:
        run = LineString([at(x, -2 * FADE / G), at(x, 2 * FADE / G)])
        for q in strands(run.intersection(field).difference(keepout)):
            lines.poly(q.coords)
    for y in HORIZONTALS:
        run = LineString([at(-2 * FADE / G, y), at(2 * FADE / G, y)])
        for q in strands(run.intersection(field).difference(keepout)):
            lines.poly(q.coords)
    fade = s.radial_gradient([(0, BG_ALT), (R * 1.2 / FADE, BG_ALT), (1, BG)], c, FADE)
    s.stroke(lines, fade, 1.2)

    # center lines of the bubble: drawn outside the mark, scored across it
    axes = unary_union(
        [
            LineString([(c.x, c.y - R - 60), (c.x, c.y + R + 60)]),
            LineString([(c.x - R - 60, c.y), (c.x + R + 60, c.y)]),
        ]
    )
    cl = P()
    for q in strands(axes.difference(keepout)):
        cl.poly(q.coords)
    s.stroke(cl, UI, 1.2, dash=DASHDOT)

    if s.params.dimensions:
        # dimensions: the bubble's width below, one stroke's width above on the stem's edges
        ext, dl, heads = P(), P(), P()
        yd = c.y + R + 80
        for x in (c.x - R, c.x + R):
            ext.M(x, c.y + R + 14).V(yd + 12)
        dl.M(c.x - R, yd).H(c.x + R)
        heads.arrowhead((c.x + R, yd), ARROW, deg=0, width=ARROW_W)
        heads.arrowhead((c.x - R, yd), ARROW, deg=180, width=ARROW_W)
        x0, x1 = at(STEM_X - HALF, 0).x, at(STEM_X + HALF, 0).x
        yt = c.y - R - 44
        for x in (x0, x1):
            ext.M(x, c.y - math.sqrt(R * R - (x - c.x) ** 2) - 12).V(yt - 12)
        dl.M(x0 - 34, yt).H(x0).M(x1, yt).H(x1 + 34)
        heads.arrowhead((x0, yt), ARROW, deg=0, width=ARROW_W)
        heads.arrowhead((x1, yt), ARROW, deg=180, width=ARROW_W)
        s.stroke(ext, UI, 1.2)
        s.stroke(dl, UI_ALT, 1.2)
        s.fill(heads, UI_ALT)

    # the mark, scored with the circle it squares off, its center lines, one radius and the
    # centers of the hook and the loop
    s.fill(P().shape(bubble.difference(f)), UI)
    clear = f.union(loop).buffer(3)
    circle = LineString(arc((c.x, c.y), R, 90, 180))
    scored = P()
    for q in strands(unary_union([axes, circle]).intersection(bubble.buffer(-3)).difference(clear)):
        scored.poly(q.coords)
    s.stroke(scored, BG, 1.2, dash=DASHDOT)
    marks, tips = P(), P()
    for x, y in (HOOK, LOOP):
        p = at(x, y)
        marks.M(p.x - 9, p.y).H(p.x + 9).M(p.x, p.y - 9).V(p.y + 9)
    if s.params.dimensions:
        rim = polar(c, R, deg=RADIUS_DEG)
        for q in strands(LineString([c, rim]).difference(clear)):
            marks.poly(q.coords)
        tips.arrowhead(rim, ARROW, deg=RADIUS_DEG, width=ARROW_W)
    s.stroke(marks, BG, 1.2)
    s.fill(tips, BG)
    s.fill(P().shape(loop), ACCENT)

"""Richmond's ruler-and-compass polygons, with every compass arc and ruled line left on the sheet."""

import math
from dataclasses import dataclass

from shapely import LineString, clip_by_rect
from shapely.geometry.base import BaseGeometry

from walldye import (
    ACCENT,
    BG_ALT,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    Path,
    Rect,
    Vec,
    design,
    knob,
    polar,
)

R = 300  # radius of the circle the polygon is inscribed in


class Construction(Params):
    sides: int = knob(default=5, choices=(5, 17), doc="the regular polygon constructed")


VARIANTS = {"seventeen": Construction(sides=17)}


@dataclass(frozen=True)
class Sheet:
    """One construction, sorted by pen: `ruled` lines run to the canvas edges (BG_ALT),
    `drawn` holds the arcs and segments (UI_ALT), `centres` get a cross and `found` a dot
    (UI_HI), and the polygon through `verts` is inked with a dot on the vertex `first` found."""

    ruled: Path
    drawn: Path
    centres: list[Vec]
    found: list[Vec]
    verts: list[Vec]
    first: Vec


def across(p: Vec, q: Vec, frame: Rect) -> BaseGeometry:
    """The line through p and q, clipped to frame."""
    reach = (q - p).unit() * (frame.w + frame.h)
    return clip_by_rect(LineString([p - reach, p + reach]), frame.x, frame.y, frame.x1, frame.y1)


def aim(c: Vec, p: Vec, half: float) -> tuple[float, float]:
    """The range of screen degrees `half` either side of the direction from c to p."""
    a = math.degrees(math.atan2(p.y - c.y, p.x - c.x))
    return a - half, a + half


def pentagon(o: Vec, frame: Rect) -> Sheet:
    """Richmond's pentagon: M halves the left radius OA, the bisector of angle OMP (P at the top)
    meets OP at Q, and the chord through Q gives the first vertex; the rest are stepped off."""
    top, a, m = o + (0, -R), o + (-R, 0), o + (-R / 2, 0)
    half = math.degrees(math.atan2(R, R / 2)) / 2  # half of angle OMP
    rho = R / 2  # compass opening for the bisection; its first mark lands on O
    b2 = polar(m, rho, deg=-2 * half)  # its second mark, on MP
    x = polar(m, 2 * rho * math.cos(math.radians(half)), deg=-half)  # arcs from O and b2 cross
    q = o + (0, -R / 2 * math.tan(math.radians(half)))
    h = R * math.sqrt(3) / 2
    vesica = (Vec(m.x, o.y - h), Vec(m.x, o.y + h))  # arcs about A and O cross here, over M
    v = [polar(o, R, bearing=72 * k) for k in range(5)]

    ruled = P()
    for p0, p1 in ((a, o), (top, o), vesica, (m, top), (m, x)):
        ruled.shape(across(p0, p1, frame))
    # Only the diameter runs to the edges; a second full-width horizon would clutter the empty side.
    ruled.M(o.x - R - 110, q.y).H(o.x + R + 110)

    drawn = P().circle(o, R)
    drawn.M(o.x - R - 40, o.y).H(o.x + R + 40).M(o.x, o.y - R - 40).V(o.y + R + 40)
    drawn.M(m.x, vesica[0].y - 30).V(vesica[1].y + 30).M(m).L(top)
    drawn.M(v[4].x - 30, q.y).H(v[1].x + 30)
    drawn.arc(a, R, deg=(-72, 72))
    drawn.arc(m, rho, deg=(-2 * half - 7, 7))
    drawn.M(m).L(polar(m, abs(x - m) + 40, deg=-half))
    for c in (o, b2):
        drawn.arc(c, rho, deg=aim(c, x, 9))
    side = abs(v[1] - v[0])
    for c, t in ((v[1], v[2]), (v[4], v[3]), (v[0], v[1]), (v[0], v[4])):
        drawn.arc(c, side, deg=aim(c, t, 8))
    # The Q chord yields v[1] first.
    return Sheet(ruled, drawn, [o, a, m, b2, v[0], v[1], v[4]], [q, x, *vesica, *v[1:]], v, v[1])


def heptadecagon(o: Vec, frame: Rect) -> Sheet:
    """Richmond's 17-gon: OI is a quarter of OB, angle OIE a quarter of OIA and EIF 45 degrees;
    the circle on AF cuts OB at K, the circle about E through K cuts OA at N3 and N5, and the
    ordinates there meet the circle at vertices 3 and 5."""
    a, b, i = o + (R, 0), o + (0, -R), o + (0, -R / 4)
    oia = math.degrees(math.atan2(R, R / 4))  # IO points down the page, at 90 screen degrees
    e = o + (R / 4 * math.tan(math.radians(oia / 4)), 0)
    f = o + (-R / 4 * math.tan(math.radians(45 - oia / 4)), 0)
    mid, rad = (a + f) / 2, abs(a - f) / 2
    k = o + (0, -math.sqrt(rad**2 - (mid.x - o.x) ** 2))
    ek = abs(k - e)
    feet = (e + (ek, 0), e - (ek, 0))  # N3, N5
    p3, p5 = (n + (0, -math.sqrt(R**2 - (n.x - o.x) ** 2)) for n in feet)
    v = [polar(o, R, deg=-360 * j / 17) for j in range(17)]
    rho = R / 4  # compass opening at I; its first mark lands on O
    # Quartering OIA: halve it, then halve the half. Each halving crosses arcs from O and from a
    # nick on the arc about I; the second crossing lies on IE.
    nicks = [polar(i, rho, deg=90 - oia), polar(i, rho, deg=90 - oia / 2)]
    crosses = [
        polar(i, 2 * rho * math.cos(math.radians(h)), deg=90 - h) for h in (oia / 2, oia / 4)
    ]

    ruled = P()
    for p0, p1 in ((a, o), (b, o), (i, a), (i, e), (i, f)):
        ruled.shape(across(p0, p1, frame))

    drawn = P().circle(o, R)
    drawn.M(o.x - R - 40, o.y).H(o.x + R + 40).M(o.x, o.y - R - 40).V(o.y + R + 40)
    drawn.M(i).L(a).M(i).L(f + (f - i).unit() * 30)
    for x in crosses:
        drawn.M(i).L(x + (x - i).unit() * 20)
    drawn.arc(mid, rad, deg=(172, 368)).arc(e, ek, deg=(172, 368))
    for n, p in zip(feet, (p3, p5), strict=True):
        drawn.M(n.x, n.y + 30).V(p.y - 30)
    drawn.arc(i, rho, deg=(90 - oia - 7, 90 - oia / 4 + 45 + 7))  # from IA round past IF
    for nick, x in zip(nicks, crosses, strict=True):
        for c in (o, nick):
            drawn.arc(c, rho, deg=aim(c, x, 12))
    side = abs(v[1] - v[0])
    for j in range(17):
        if (j + 1) % 17 not in (0, 3, 5):
            drawn.arc(v[j], side, deg=aim(v[j], v[(j + 1) % 17], 8))
    return Sheet(ruled, drawn, [o, i, *nicks, e, mid], [k, f, *feet, *crosses, a, p3, p5], v, p3)


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Construction]) -> None:
    o = s.pick(landscape=(1340 / 1920, 520 / 1080), portrait=(0.5, 0.44))
    build = pentagon if s.params.sides == 5 else heptadecagon
    sheet = build(o, s.inset(0))

    s.stroke(sheet.ruled, BG_ALT, 1)
    s.stroke(sheet.drawn, UI_ALT, 1.5)
    marks = P()
    for c in sheet.centres:
        marks.M(c.x - 9, c.y).H(c.x + 9).M(c.x, c.y - 9).V(c.y + 9)
    s.stroke(marks, UI_HI, 1.4)
    s.fill(P().dots(sheet.found, 2.5), UI_HI)

    s.stroke(P().poly(sheet.verts, closed=True), ACCENT, 2.5, join="round")
    s.fill(P().circle(sheet.first, 7), ACCENT)

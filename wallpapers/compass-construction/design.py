"""Richmond's ruler-and-compass pentagon, with every compass arc and ruled line left on the sheet."""

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
    Path,
    Rect,
    Vec,
    design,
    polar,
)

R = 300  # radius of the circle the polygon is inscribed in


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


@design(aspects="any")
def draw(s: Canvas) -> None:
    o = s.pick(landscape=(1340 / 1920, 520 / 1080), portrait=(0.5, 0.44))
    sheet = pentagon(o, s.inset(0))

    s.stroke(sheet.ruled, BG_ALT, 1)
    s.stroke(sheet.drawn, UI_ALT, 1.5)
    marks = P()
    for c in sheet.centres:
        marks.M(c.x - 9, c.y).H(c.x + 9).M(c.x, c.y - 9).V(c.y + 9)
    s.stroke(marks, UI_HI, 1.4)
    s.fill(P().dots(sheet.found, 2.5), UI_HI)

    s.stroke(P().poly(sheet.verts, closed=True), ACCENT, 2.5, join="round")
    s.fill(P().circle(sheet.first, 7), ACCENT)

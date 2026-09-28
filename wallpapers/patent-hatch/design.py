"""A patent figure of a ball in a cone on a column and plate, shaded only by spaced lines that tighten into the shade, with leaders out to a column of dashes."""

import itertools
import math
from collections.abc import Callable, Sequence

from shapely import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, ACCENT_3, UI_ALT, UI_HI, Canvas, P, Vec, design, ladder, polar
from walldye.geom import Affine, ribbon

# The figure is drawn in a 1080-tall box with the apparatus axis at x = 0, then placed by one
# transform.
K = 0.27  # ellipse squash: how far we look down on the apparatus
PLATE_Y, PLATE_R, PLATE_T = 806, 200, 22
CYL_R, CYL_TOP = 100, 494
RIM_Y, RIM_R = 329, 120
SPH_Y, SPH_R = 298, 98
LIGHT = (-0.55, -0.5, 0.67)  # upper left, towards the viewer
ARCS = 26  # hatching arcs on the ball
TONES = ladder((ACCENT, ACCENT_3), 5)  # ball arcs, from the highlight out into the shade
# leaders: (start on the part, end y); the ball's own leader is drawn separately
LEADERS = (
    ((52, CYL_TOP + 110), 520),
    ((76, CYL_TOP + 240), 680),
    ((PLATE_R * math.cos(0.45), PLATE_Y + K * PLATE_R * math.sin(0.45) + PLATE_T / 2), 840),
    ((46, RIM_Y + 64), 360),
)

type Pts = list[tuple[float, float]]


def ellipse(cy: float, r: float, a0: float = 0.0, a1: float = 2 * math.pi, n: int = 160) -> Pts:
    """Points on a level circle of radius `r` at height `cy` seen from above, angle a0 to a1;
    angles in (0, pi) are the front half."""
    return [
        (r * math.cos(a0 + (a1 - a0) * i / n), cy + K * r * math.sin(a0 + (a1 - a0) * i / n))
        for i in range(n + 1)
    ]


def drum(y0: float, y1: float, r: float) -> BaseGeometry:
    """Silhouette of an upright cylinder between top y0 and bottom y1."""
    return unary_union([Polygon(ellipse(y0, r)), box(-r, y0, r, y1), Polygon(ellipse(y1, r))])


def shade(nx: float, ny: float, nz: float) -> float:
    """Darkness in [0, 1] for a surface normal under LIGHT."""
    return 1 - max(0.0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2])


def spaced(
    darkness: Callable[[float], float], lo: float, hi: float, count: int, floor: float = 0.12
) -> list[float]:
    """Parameters in [lo, hi] whose spacing tightens with darkness (a hatching CDF)."""
    n = 400
    ts = [lo + (hi - lo) * i / n for i in range(n + 1)]
    w = [max(0.0, darkness(t) - floor) ** 1.3 for t in ts]
    cdf = [0.0]
    for a, b in itertools.pairwise(w):
        cdf.append(cdf[-1] + (a + b) / 2)
    out: list[float] = []
    k, step = 1, cdf[-1] / count
    for t, c in zip(ts, cdf, strict=True):
        if c >= k * step:
            out.append(t)
            k += 1
    return out


def swell(
    pts: Sequence[tuple[float, float]], width: Callable[[float], float], body: BaseGeometry
) -> BaseGeometry:
    """Patent shade line: a band `width(u)` wide (u in [0, 1] along `pts`) just outside
    `body`, whose edge `pts` follows."""
    n = len(pts) - 1
    return Polygon(ribbon(pts, [2 * width(i / n) for i in range(n + 1)])).difference(body)


def column(y: float) -> float:
    """x of the dash at height y: the dashes sit on one gently bowed column."""
    return 492 - 36 * ((y - 520) / 320) ** 2


@design(aspects="any")
def draw(s: Canvas) -> None:
    cone_tan = math.asin(K * RIM_R / (CYL_TOP - RIM_Y))
    cone = Polygon([(0, CYL_TOP), *ellipse(RIM_Y, RIM_R, cone_tan, math.pi - cone_tan)])
    sphere = Point(0, SPH_Y).buffer(SPH_R, quad_segs=64)
    cyl = drum(CYL_TOP, PLATE_Y, CYL_R)

    hatch, outline, heavy = P(), P(), P()

    # plate: rim band hatched, hidden behind the cylinder's foot
    for u in spaced(lambda u: shade(u, 0, math.sqrt(1 - u * u)), -0.999, 0.999, 70, floor=0.25):
        y = PLATE_Y + K * PLATE_R * math.sqrt(1 - u * u)
        hatch.M(u * PLATE_R, y).V(y + PLATE_T)
    outline.shape(LineString(ellipse(PLATE_Y, PLATE_R)).difference(cyl))
    outline.poly(ellipse(PLATE_Y + PLATE_T, PLATE_R, 0, math.pi))
    # shade lines on the lower right edges, patent style; curved ones swell and fade
    foot = Polygon(ellipse(PLATE_Y + PLATE_T, PLATE_R))
    front = ellipse(PLATE_Y + PLATE_T, PLATE_R, 0, 0.62 * math.pi, 80)
    swells = [swell(front, lambda u: 1.6 * (1 - u) ** 0.8, foot)]
    outline.M(-PLATE_R, PLATE_Y).V(PLATE_Y + PLATE_T)
    heavy.M(PLATE_R, PLATE_Y).V(PLATE_Y + PLATE_T)

    # cylinder: vertical hatching, tighter into the shade;
    # two sparse lines ease the lit third into the hatching
    ruled = spaced(lambda u: shade(u, 0, math.sqrt(1 - u * u)), -0.999, 0.999, 30)
    for u in [-0.84, -0.58, *ruled]:
        dy = K * CYL_R * math.sqrt(1 - u * u)
        hatch.M(u * CYL_R, CYL_TOP + dy + 3).V(PLATE_Y + dy - 2)
    outline.shape(LineString(ellipse(CYL_TOP, CYL_R)).difference(cone))
    outline.poly(ellipse(PLATE_Y, CYL_R, 0, math.pi))
    outline.M(-CYL_R, CYL_TOP).V(PLATE_Y)
    heavy.M(CYL_R, CYL_TOP).V(PLATE_Y)

    # cone cradle: rim-to-apex rulings, stopped short so the apex stays open
    tilt = 0.55
    rulings = spaced(
        lambda t: shade(math.cos(t) * math.cos(tilt), math.sin(tilt), math.sin(t) * math.cos(tilt)),
        cone_tan,
        math.pi - cone_tan,
        26,
    )
    apex = Vec(0, CYL_TOP)
    for i, t in enumerate(rulings):
        rim = Vec(RIM_R * math.cos(t), RIM_Y + K * RIM_R * math.sin(t))
        # the shade side stops early so it doesn't merge with the heavy line at the apex
        f = (0.62 if i % 2 else 0.5) if rim.x > 20 else (0.9 if i % 2 else 0.68)
        hatch.M(rim + (apex - rim) * 0.04).L(rim + (apex - rim) * f)
    outline.poly(ellipse(RIM_Y, RIM_R, 0, math.pi))
    outline.shape(LineString(ellipse(RIM_Y, RIM_R, math.pi, 2 * math.pi)).difference(sphere))
    tx, ty = RIM_R * math.cos(cone_tan), RIM_Y + K * RIM_R * math.sin(cone_tan)
    outline.M(-tx, ty).L(apex)
    heavy.M(tx, ty).L(apex)

    # ball: arcs about the highlight, crowding into the terminator
    lit = Vec(-0.42 * SPH_R, SPH_Y - 0.45 * SPH_R)
    to_c = Vec(0, SPH_Y) - lit
    far, away = abs(to_c) + SPH_R, math.atan2(to_c.y, to_c.x)
    vis = sphere.difference(cone)
    rng = s.rng(3)
    arcs: list[tuple[int, BaseGeometry]] = []
    for k in range(ARCS):
        x = (k + 1) / ARCS
        rho = 0.5 * SPH_R + (far - 0.5 * SPH_R) * (1 - (1 - x) ** 1.8)
        # arcs open out from a short crescent near the light to a full sweep in the shade
        a0 = away - math.radians(55 + 95 * x + rng.uniform(-9, 9))
        a1 = away + math.radians(55 + 95 * x + rng.uniform(-9, 9))
        ring = LineString([polar(lit, rho, rad=a0 + (a1 - a0) * i / 60) for i in range(61)])
        arcs.append((TONES.rung(x), ring.intersection(vis)))
    outline.shape(sphere.exterior.difference(cone))
    edge = [polar((0, SPH_Y), SPH_R, deg=a) for a in range(-60, 96)]
    swells.append(swell(edge, lambda u: 1.7 * math.sin(math.pi * u) ** 0.7, sphere.union(cone)))

    lead, marks = P(), P()
    for (sx, sy), ey in LEADERS:
        ex = column(ey)
        dx = ex - sx
        lead.M(sx, sy).C(sx + dx * 0.4, sy, ex - dx * 0.45, ey, ex, ey)
        marks.M(ex + 14, ey).H(ex + 32)
    # the ball's leader starts in its unhatched highlight and leaves over the top, clear of the arcs
    ey = 178
    ex = column(ey)
    lead.M(-18, SPH_Y - 40).C(-18, SPH_Y - 150, ex - 420, ey, ex, ey)
    marks.M(ex + 14, ey).H(ex + 32)

    # the axis sits left of centre on a landscape screen; a portrait screen centres the whole
    # figure (x -200 to 524) and enlarges it
    at = s.pick(landscape=(0.396, 0.5), portrait=(0.32, 0.5))
    zoom = 1.0 if s.landscape else 1.2
    with s.group(transform=Affine.translate(at.x, at.y - 540 * zoom) @ Affine.scale(zoom)):
        s.stroke(hatch, UI_ALT, 1.2)
        with s.buckets(TONES, "stroke", stroke_width=1.3) as tones:
            for i, g in arcs:
                tones[i].shape(g)
        s.stroke(outline, UI_HI, 1.6, join="round", cap="round")
        s.stroke(heavy, UI_HI, 3, join="round", cap="round")
        sw = P()
        for g in swells:
            sw.shape(g)
        s.fill(sw, UI_HI)
        s.stroke(lead, UI_HI, 1.2, cap="round")
        s.stroke(marks, ACCENT, 3, cap="round")

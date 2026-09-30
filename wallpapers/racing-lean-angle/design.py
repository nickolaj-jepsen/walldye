"""A motorcycle tire in drafted section, rolled onto its shoulder in five positions."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from walldye import ACCENT, ACCENT_2, ACCENT_3, UI, UI_ALT, Canvas, P, Vec, design
from walldye.geom import Affine, bezier_points, hatch, parts, spline_points

type F = NDArray[np.float64]

# Section frame: millimeters, x across the tire, y up from the crown's ground contact. The
# tread is an arc of radius RHO about (0, RHO), so a lean of phi puts the ground under the tread
# point phi round from the crown, and rolling there moves that center RHO * phi sideways.
RHO = 108.0
LEAN = 66.0  # degrees, the last position
STEPS = 4  # the earlier positions sit every LEAN / STEPS degrees
SEAT, RIM_HALF = 130.0, 76.2  # 200/65 R17: section height 130 over the bead seat; 6.00 in rim
AXLE = SEAT + 17 * 25.4 / 2  # the wheel center, a 17 in rim's radius above the bead seat
LIP = (78.7, 116.5, 2.5)  # rim flange lip: center and radius
# right half, from the tread edge at 70 degrees round to the top of the flange lip
SIDE = ((102.4, 81.5), (100.4, 92.5), (95.6, 102.0), (89.4, 108.6), (83.4, 112.6), (78.7, 114.0))
# wall thickness against the outer contour's height: thick under the tread, thin in the sidewall
WALL_Y, WALL_T = (0, 30, 50, 71, 88, 100, 112), (13, 13, 12, 8.5, 6.5, 6.5, 7.5)
# inner liner round the bead, and the carcass ply wrapped round the bead core and turned back up
HEEL = ((81.0, 104.6), (74.5, 108.0), (68.8, 111.4), (64.2, 115.6), (62.0, 120.5), (61.5, 125.5))
TURN = (
    (83.5, 107.0),
    (77.0, 110.6),
    (70.8, 114.5),
    (67.2, 118.2),
    (65.6, 121.8),
    (65.3, 125.4),
    (66.4, 127.6),
    (69.0, 128.2),
    (71.8, 127.6),
    (73.3, 125.2),
    (73.8, 121.0),
    (74.6, 115.8),
    (78.2, 111.6),
    (83.0, 109.2),
)
CORE = (69.4, 123.3)  # bead core: 4 by 3 wires, 1.6 apart
# rim, tire side, from just past the middle of the well (so the halves overlap) out to the flange,
# with the fillet radius at each bend
RIM = ((-2, 150), (28, 150), (40, 133), (56, SEAT), (RIM_HALF, SEAT), (RIM_HALF, 116.5))
FILLETS = (8, 8, 6, 1.5)


def arc(r: float, a0: float, a1: float, n: int) -> F:
    """Points on the circle of radius `r` about the tread center, from `a0` to `a1` degrees round
    from the crown, positive to the right."""
    a = np.radians(np.linspace(a0, a1, n))
    return np.column_stack([r * np.sin(a), RHO - r * np.cos(a)])


def both(half: F) -> F:
    """A right half ordered from the middle outward, joined to its mirror image: one line from
    the left end through the middle to the right end."""
    return np.vstack([(half * (-1, 1))[::-1], half[1:]])


def inward(line: F, depth: F) -> F:
    """`line` moved `depth` to its left, into the tire for a contour running crown outward."""
    d = np.gradient(line, axis=0)
    n = np.column_stack([-d[:, 1], d[:, 0]]) / np.hypot(d[:, 0], d[:, 1])[:, None]
    return line + n * depth[:, None]


def section() -> tuple[F, F, F, F, F, F]:
    """The tire's outer contour, inner liner and carcass ply, each bead to bead, the belt cords
    and the bead wires as points, and the outline of the tread rubber, surface to belt, that
    has met the ground by the last position, all in the section frame."""
    side = spline_points(np.vstack([arc(RHO, 0, 70, 15), SIDE]), 8)
    cx, cy, cr = LIP
    a = np.radians(np.linspace(-90, -180, 9))
    lip = np.column_stack([cx + cr * np.cos(a), cy + cr * np.sin(a)])
    outer = np.vstack([side, lip[1:], [(RIM_HALF, SEAT), (HEEL[-1][0], SEAT)]])
    t = np.interp(side[:, 1], WALL_Y, WALL_T)
    wall = side[:, 1] < 107  # the offset stops where the bead begins
    liner = np.vstack([inward(side, t)[wall], spline_points((*HEEL, (HEEL[-1][0], SEAT)), 6)])
    ply = np.vstack([inward(side, t - 2.7)[wall], spline_points(TURN, 6)])
    belt = inward(side, t - 5.0)[side[:, 1] < 55][::2]
    wires = np.array(
        [(CORE[0] + (i - 1.5) * 1.6, CORE[1] + (j - 1) * 1.6) for i in range(4) for j in range(3)]
    )
    met = np.degrees(np.arctan2(side[:, 0], RHO - side[:, 1])) <= LEAN
    band = np.vstack([side[met], inward(side, t - 5.0)[met][::-1]])
    return (
        both(outer),
        both(liner),
        both(ply),
        both(belt),
        np.vstack([wires * (-1, 1), wires]),
        band,
    )


def filleted(pts: tuple[tuple[float, float], ...], radii: tuple[float, ...]) -> F:
    """The polyline through `pts` with each inner corner rounded: a quadratic curve from `r` / tan
    of half the corner angle before the corner to as far after it, `radii` in corner order."""
    p = np.asarray(pts, dtype=np.float64)
    out = [p[:1]]
    for i, r in enumerate(radii, 1):
        u, v = p[i - 1] - p[i], p[i + 1] - p[i]
        u, v = u / np.hypot(*u), v / np.hypot(*v)
        d = r / math.tan(math.acos(float(np.clip(u @ v, -1, 1))) / 2)
        out.append(bezier_points([p[i] + u * d, p[i], p[i] + v * d], 8))
    return np.vstack([*out, p[-1:]])


def placed(phi: float) -> Affine:
    """Section frame to the world (mm, y up, ground at 0) for a lean of `phi` degrees to the
    right, rolled from upright without slipping."""
    t = math.radians(phi)
    return Affine.translate(RHO * t, RHO) @ Affine.rotate(rad=-t) @ Affine.translate(0, -RHO)


def moved(g: BaseGeometry, m: Affine) -> BaseGeometry:
    """`g` carried through `m`."""
    return shapely.transform(g, m.apply)


@design(aspects="any")
def draw(s: Canvas) -> None:
    outer, liner, ply, belt, wires, band = section()
    tire = Polygon(np.vstack([outer, liner[::-1]])).buffer(0)
    half = LineString(filleted(RIM, FILLETS)).buffer(5, single_sided=True, join_style="round")
    half = half.union(Point(LIP[:2]).buffer(LIP[2], quad_segs=12))
    rim = half.union(shapely.transform(half, lambda xy: xy * (-1, 1)))
    rim = rim.buffer(2.5).buffer(-2.5)
    solid = shapely.unary_union([Polygon(outer).buffer(0), tire, rim.convex_hull])

    # the figure's box in the world: the upright section's left shoulder to the last wheel center
    span = RHO * math.radians(LEAN)
    x0, x1, y1 = -RHO, placed(LEAN)((0, AXLE)).x + 10, AXLE + 10
    k = 1.95 if s.landscape else 1.85
    at = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.52))
    world = Affine.translate(at.x - k * (x0 + x1) / 2, at.y + k * y1 / 2) @ Affine.scale(k, -k)
    final = world @ placed(LEAN)

    # the earlier positions in hairline, hidden behind the final one, each profile stopping
    # partway up the sidewall; a leaned position's wheel plane shows only where it leaves the
    # final section for its hub, since the stubs below it would knot round the first contact
    hull = moved(solid, final).buffer(6)
    profile = outer[outer[:, 1] <= 98]
    ghosts, planes = P(), P()
    for i in range(STEPS):
        m = world @ placed(LEAN * i / STEPS)
        ghosts.shape(LineString(m.apply(profile)).difference(hull))
        plane = LineString(m.apply([(0, -14), (0, AXLE + 6)])).difference(hull)
        for g in parts(plane):
            if i == 0 or g.distance(Point(m((0, AXLE)))) < 1:
                planes.shape(g)

    # the final section: ply, belt cords and bead wires, with the tread rubber outside the ply
    # hatched shoulder to shoulder and the hatch in the tread that has met the ground lit; the
    # rim is a mating part, in phantom line
    carcass = LineString(ply)
    cords = np.vstack([belt, wires])
    keep = shapely.unary_union(
        [carcass.buffer(1.2), LineString(liner).buffer(3.9), *(Point(c).buffer(1.3) for c in cords)]
    )
    wedge = Polygon(np.vstack([[(0, RHO)], arc(200, -71, 71, 30)]))
    rubber = moved(tire.difference(keep) & wedge, final)
    lit = moved(Polygon(band).buffer(0), final)
    lines, glow = P(), P()
    for path, region, pitch in ((lines, rubber.difference(lit), 5.5), (glow, rubber & lit, 3)):
        for seg in hatch(region.buffer(-1.2), pitch, deg=45):
            if math.hypot(*(seg[1] - seg[0])) >= 6:  # no specks in the corners
                path.poly(seg)

    # the ground with its contact points, and the wheel center's path ticked at thirds of a step
    def hub(a: float) -> Vec:
        return world(placed(a)((0, AXLE)))

    g0, g1 = world((0, 0)), world((span, 0))
    ground = P().M(world((-RHO - 12, 0))).L(world((span + RHO + 12, 0)))
    ticks, hubs = P(), P()
    for i in range(STEPS + 1):
        x = world((RHO * math.radians(LEAN * i / STEPS), 0))
        ticks.M(x).L(x + (0, 9))
    scale = P().poly([hub(a) for a in np.linspace(0, LEAN, 133).tolist()])
    for i in range(3 * STEPS + 1):
        a = LEAN * i / (3 * STEPS)
        if i % 3 == 0 and i < 3 * STEPS:
            hubs.circle(hub(a), 5)
        elif i % 3:
            scale.M(hub(a)).L(hub(a) + (hub(a + 0.1) - hub(a - 0.1)).unit().perp() * 8)

    s.stroke(ground, UI, 1.2)
    s.stroke(ghosts, UI, 1.3, join="round")
    s.stroke(planes, UI, 1.0, dash=(22, 5, 3, 5))
    s.stroke(lines, UI, 1.0)
    s.stroke(glow, ACCENT_2, 1.2)
    s.stroke(P().shape(moved(carcass, final)), UI_ALT, 1.1)
    s.fill(P().dots(final.apply(cords), 0.65 * k), UI_ALT)
    s.stroke(P().shape(moved(rim, final)), UI, 1.1, join="round", dash=(14, 4, 3, 4, 3, 4))
    s.stroke(P().shape(moved(tire, final)), UI_ALT, 1.6, join="round")
    s.stroke(scale, UI, 1.2)
    s.stroke(hubs, UI, 1.3)
    s.stroke(P().M(final((0, -14))).L(final((0, AXLE + 6))), UI_ALT, 1.2, dash=(22, 5, 3, 5))
    s.stroke(P().circle(hub(LEAN), 5), UI_ALT, 1.3)
    s.stroke(ticks, UI_ALT, 1.2)
    s.stroke(P().M(g0).L(g1), ACCENT_3, 2)
    s.stroke(P().poly(final.apply(arc(RHO, 0, LEAN, 67))), ACCENT, 4.5, cap="round")

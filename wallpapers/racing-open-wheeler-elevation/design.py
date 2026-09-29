"""A 2026 Formula 1 car as a patent-sheet side elevation in hairlines; detail A hatches the three-element rear wing and dashes its flap at the low-drag angle."""

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray
from shapely import LineString, Point, Polygon, unary_union

from walldye import ACCENT, ACCENT_HI, UI, UI_ALT, UI_HI, Canvas, P, Path, Vec, design
from walldye.geom import Affine, bezier_points, hatch, spline_points
from walldye.pixel import glyphs, text_width

# The figure is laid out on a 1920x1080 sheet and centered on wider screens.
K, X0, GY = 0.225, 290, 730  # px per mm, nose tip, ground line
BUB, BR = Vec(1640, 300), 165  # detail A
FIG_CX = 1002  # middle of the figure, from the ground line's start to detail A's rim

# Car coordinates in mm, as the 2026 technical regulations set them: x back from the front
# axle, z up from the reference plane under the floor, which sits 65 above the ground.
WB, NOSE_X, TAIL_X, TOP_Z, GROUND = 3400, -1300, 4200, 970, -65
FRONT, REAR = (0, 290), (WB, 285)  # axle centers
R_FRONT, R_REAR, RIM_LIP, RIM_SEAT = 352.5, 355, 248, 231  # tires on 18-inch rims

# Nose from the chassis floor round the tip to the cockpit, then the cockpit rim and headrest.
NOSE = (
    (300, 216),
    (0, 222),
    (-300, 208),
    (-600, 178),
    (-1000, 138),
    (-1220, 128),
    (-1285, 140),
    (-1300, 178),
    (-1286, 212),
    (-1240, 234),
    (-1100, 290),
    (-800, 395),
    (-400, 510),
    (0, 590),
    (400, 632),
    (825, 645),
)
RIM = ((825, 645), (1150, 648), (1330, 656), (1470, 692), (1600, 740), (1700, 768))
# The airbox, a rounded peak over the roll hoop with its inlet facing forward, and the engine
# cover falling away from it towards the gearbox. The fin stands on the cover's spine, its top
# edge sloping down to a trailing edge ahead of the rear axle.
TOP = (
    (1700, 768),
    (1706, 830),
    (1716, 900),
    (1735, 946),
    (1768, 966),
    (1810, 970),
    (1880, 961),
    (2050, 918),
    (2300, 852),
    (2650, 772),
    (3000, 692),
    (3300, 606),
    (3350, 598),
)
INLET_LIP = ((1716, 842), (1726, 900), (1746, 938))
FIN = (
    (2050, 918),
    (2300, 912),
    (2600, 890),
    (2900, 858),
    (3150, 832),
    (3222, 825),
    (3246, 805),
    (3258, 760),
    (3272, 680),
    (3284, 600),
)
HALO = ((735, 668), (790, 765), (870, 828), (1100, 848), (1400, 850), (1530, 830), (1585, 770))
HELMET, VISOR = (1420, 745), ((1308, 772), (1420, 792), (1515, 772))
# The mirror pod, and its rear stay down to the sidepod's shoulder.
MIRROR = ((880, 630), (1048, 628), (1052, 700), (886, 702))  # straddling the cockpit rim
STAY, STAY_W = ((1000, 660), (1215, 568)), 28
# Sidepod: inlet lip, upper edge falling to the rear axle, and the undercut to the floor.
INLET = ((1080, 585), (1052, 565), (1040, 480), (1046, 380), (1072, 318), (1120, 302))
POD = ((1080, 585), (1400, 596), (1700, 594), (2200, 520), (2700, 444), (3100, 383), (3300, 352))
UNDERCUT = ((1120, 302), (1400, 228), (1800, 160), (2300, 110), (2750, 82))
# The in-washing board ahead of the sidepod, standing on the floor from its leading edge, and
# the floor's upper edge running back from it, rising at the floor's rear corner.
BOARD = (
    (660, 50),
    (660, 250),
    (660, 400),
    (666, 426),
    (688, 439),
    (730, 440),
    (764, 416),
    (800, 330),
    (880, 252),
    (1050, 194),
    (1350, 150),
)
FLOOR_TOP = ((1350, 150), (1600, 92), (1850, 60), (2100, 50), (2740, 50))
RAMP = ((2740, 50), (2960, 50), (3065, 86))  # a quadratic
FLOOR_NOSE = ((360, 215), (395, 180), (418, 100), (440, 30), (480, 4), (540, 0))
TAIL_TOP = ((3700, 490), (3800, 432), (3905, 381), (4000, 374), (4200, 372))
TAIL_UNDER = ((4200, 238), (3950, 205), (3760, 172))
# Endplates: the front one's top rises to z 375 and its back follows the tire at r 462.5.
FW_TOP = ((-1050, 75), (-1056, 230), (-1040, 256), (-900, 312), (-760, 368), (-700, 375))
FW_ARC = (Vec(0, 360), 462.5)
RW_PLATE = (
    (3552, 721),
    (3552, 830),
    (3562, 862),
    (3590, 878),
    (3630, 880),
    (4150, 880),
    (4150, 625),
    (4042, 300),
    (3850, 252),
    (3745, 252),
)
UPPER_ARM, LOWER_ARM = ((0, 455), (720, 430)), ((0, 250), (720, 274))
CG = (1870, 220)  # 45% of the mass on the front axle

# NACA sections: chord, camber, camber position, thickness, angle of attack (deg), leading edge.
# Front wing, the center of the mainplane ahead of the endplate, then mainplane and two flaps.
FW_CENTER = (440, 0.04, 0.4, 0.08, 2, (-1287, 88))
FRONT_WING = (
    (300, 0.05, 0.4, 0.08, 3, (-1045, 112)),
    (170, 0.06, 0.4, 0.10, 15, (-760, 143)),
    (140, 0.06, 0.4, 0.11, 29, (-610, 197)),
)
# Rear wing mainplane and the two-element flap, from the mainplane's leading edge at `RW_AT`.
# In straight mode the flap turns `OPEN` degrees flatter about `PIVOT`, in its rear half.
REAR_WING = (
    (245, 0.06, 0.40, 0.14, 3, (0, 0)),
    (148, 0.07, 0.40, 0.13, 15, (234, 29)),
    (108, 0.07, 0.40, 0.13, 28, (368, 76)),
)
RW_AT, PIVOT, OPEN = (3565, 752), (420, 100), 20
DS = 0.57  # detail A, px per mm


def naca(
    chord: float,
    m: float,
    p: float,
    t: float,
    aoa: float,
    lead: tuple[float, float],
    n: int = 60,
) -> NDArray[np.float64]:
    """Closed outline of an inverted (downforce) NACA 4-digit section in y-up units: camber `m`
    at `p` of the chord, thickness `t`, leading edge at `lead`, trailing edge raised `aoa`
    degrees. The first and last points are the trailing edge, point n - 1 the leading edge."""
    b = np.linspace(0, math.pi, n)
    x = (1 - np.cos(b)) / 2
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.126 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    fore = x < p
    yc = np.where(
        fore, m / p**2 * (2 * p * x - x**2), m / (1 - p) ** 2 * (1 - 2 * p + 2 * p * x - x**2)
    )
    th = np.arctan(np.where(fore, 2 * m / p**2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x)))
    upper = np.column_stack([x - yt * np.sin(th), yc + yt * np.cos(th)])
    lower = np.column_stack([x + yt * np.sin(th), yc - yt * np.cos(th)])
    xy = np.concatenate([upper[::-1], lower[1:]]) * (1, -1)  # suction side underneath
    place = Affine.translate(*lead) @ Affine.rotate(deg=aoa) @ Affine.scale(chord)
    return place.apply(xy)


def rounded(pts: NDArray[np.float64], r: float) -> Polygon:
    """The polygon through `pts` with its convex corners rounded to radius `r`."""
    return Polygon(pts).buffer(-r, quad_segs=8).buffer(r, quad_segs=8)


def cross(d: Path, c: Vec, r: float) -> None:
    """A center mark: two strokes of half-length `r` through `c`."""
    d.M(c.x - r, c.y).H(c.x + r).M(c.x, c.y - r).V(c.y + r)


def dimension(s: Canvas, d: Path, heads: Path, xa: float, xb: float, y: int, label: str) -> None:
    """A horizontal dimension from `xa` to `xb` at height `y`: extension lines down from the
    ground, arrowheads, and `label` in a break at the middle."""
    w = text_width(label, font="8x16", px=1)
    mid = (xa + xb) / 2
    d.M(xa, GY + 8).V(y + 8).M(xb, GY + 8).V(y + 8)
    d.M(xa, y).H(mid - w / 2 - 8).M(mid + w / 2 + 8, y).H(xb)
    heads.arrowhead((xa, y), 7, deg=180, width=2.6).arrowhead((xb, y), 7, deg=0, width=2.6)
    glyphs(s, label, UI_HI, at=(round(mid - w / 2), y - 8), font="8x16", px=1)


@design(aspects=("16:9", "16:10", "21:9", "32:9"))
def draw(s: Canvas) -> None:
    m = Affine.translate(X0, GY) @ Affine.scale(K, -K) @ Affine.translate(-NOSE_X, -GROUND)

    def curve(pts: ArrayLike, n: int = 14) -> NDArray[np.float64]:
        return spline_points(m.apply(pts), n)

    def line(pts: ArrayLike, n: int = 14) -> LineString:
        return LineString(curve(pts, n))

    with s.group(transform=Affine.translate(round(s.w / 2 - FIG_CX), 0)):
        hubs = [m(FRONT), m(REAR)]
        radii = [R_FRONT * K, R_REAR * K]
        hidden = unary_union([Point(c).buffer(r + 5, quad_segs=64) for c, r in zip(hubs, radii)])

        # Hidden-line work: the tires, endplates, board, mirror and halo tube stand in front.
        (cx, cz), cr = FW_ARC
        ang = np.linspace(math.asin((375 - cz) / cr), math.asin((75 - cz) / cr), 24)
        arc = np.column_stack([cx - cr * np.cos(ang), cz + cr * np.sin(ang)])
        fw_edge = np.concatenate([spline_points(FW_TOP, 10), arc])
        front = rounded(m.apply(fw_edge), 3)
        rear = rounded(m.apply(RW_PLATE), 6)
        board = Polygon(np.concatenate([curve(BOARD, 8), m.apply([(1350, 40), (660, 40)])]))
        mirror = rounded(m.apply(MIRROR), 6)
        pod = Polygon(np.concatenate([curve(POD), m.apply([(3300, 0), (1080, 0)])]))
        stay = LineString(m.apply(STAY)).buffer(STAY_W * K / 2, cap_style="flat")
        stay = stay.difference(mirror).difference(pod)
        tube = LineString(curve(HALO)).buffer(3.2, cap_style="flat", join_style="round")
        body = Polygon(np.concatenate([curve(NOSE), curve(RIM), m.apply([(1700, 0), (300, 0)])]))
        helmet = Point(m(HELMET)).buffer(120 * K, quad_segs=64)

        outline, fine, wing = P(), P(), P()
        outline.shape(front.exterior).shape(mirror.exterior)
        outline.shape(rear.exterior.difference(hidden))
        outline.shape(line(NOSE).difference(hidden).difference(front).difference(mirror))
        outline.shape(line(RIM).difference(tube).difference(mirror).difference(stay))
        outline.shape(line(TOP).difference(hidden))
        wing.shape(line(FIN).difference(hidden))  # a thin panel, drawn like the wings
        outline.shape(tube.exterior.difference(body).difference(mirror))
        floor = np.concatenate([curve(FLOOR_NOSE, 8), m.apply([(3065, 0), (3065, 85)])])
        outline.shape(LineString(floor).difference(hidden).difference(board))
        upper = [curve(BOARD + FLOOR_TOP[1:], 8), bezier_points(m.apply(RAMP), 12)[1:]]
        outline.shape(LineString(np.concatenate(upper)).difference(hidden))
        tail = np.concatenate([curve(TAIL_TOP, 10), curve(TAIL_UNDER, 10)])
        outline.shape(LineString(tail).difference(hidden).difference(rear))
        outline.shape(line(INLET, 8).difference(board))

        fine.M(200, GY).H(1600)  # ground line
        fine.shape(line(POD).difference(hidden))
        fine.shape(line(UNDERCUT).difference(hidden).difference(board))
        fine.shape(helmet.exterior.difference(body).difference(tube))
        fine.shape(line(VISOR, 6).difference(tube))
        fine.shape(line(INLET_LIP, 6))
        for side in (-1, 1):  # the stay's two edges, from the pod down into the sidepod
            fine.shape(
                LineString(m.apply(STAY))
                .offset_curve(side * STAY_W * K / 2)
                .intersection(stay.buffer(0.5))
            )
        for arm in (UPPER_ARM, LOWER_ARM):  # front wishbones, from behind the tire
            fine.shape(LineString(m.apply(arm)).difference(hidden).difference(board))
        for sec in FRONT_WING:
            wing.poly(m.apply(naca(*sec, n=24)), closed=True)
        wing.shape(Polygon(m.apply(naca(*FW_CENTER, n=24))).exterior.difference(front))
        rw = Affine.translate(*RW_AT)
        for sec in REAR_WING:
            wing.poly(m.apply(rw.apply(naca(*sec, n=24))), closed=True)

        # wheels: tire, rim lip and hub; the rim's bead seat shares the thinner leader stroke
        rings, lips = P(), P()
        for c, r in zip(hubs, radii):
            rings.circle(c, r).circle(c, RIM_LIP * K).circle(c, 45 * K)
            lips.circle(c, RIM_SEAT * K)
            cross(fine, c, 16)
        cross(fine, m(CG), 14)  # center of gravity
        fine.circle(m(CG), 5)

        # dimensions: wheelbase and overall length, and height over the reference plane
        heads = P()
        dimension(s, fine, heads, hubs[0].x, hubs[1].x, GY + 58, str(WB))
        dimension(s, fine, heads, X0, m((TAIL_X, 0)).x, GY + 98, str(TAIL_X - NOSE_X))
        hx, htop, yref = X0 - 60, m((0, TOP_Z)).y, m((0, 0)).y
        mid = (yref + htop) / 2
        fine.M(m((1799, 0)).x - 16, htop).H(hx - 8).M(X0 - 12, yref).H(hx - 8)
        fine.M(hx, yref).V(mid + 22).M(hx, mid - 22).V(htop)
        heads.arrowhead((hx, htop), 7, deg=-90, width=2.6)
        heads.arrowhead((hx, yref), 7, deg=90, width=2.6)

        # detail A: the rear wing enlarged, its flap drawn again at the straight-mode angle
        local = [naca(*q) for q in REAR_WING]
        turn = Affine.rotate(deg=-OPEN, about=PIVOT)
        opened = [turn.apply(q) for q in local[1:]]
        pts = np.concatenate(local + opened)
        ctr = (pts.min(0) + pts.max(0)) / 2
        sec = Affine.translate(*BUB) @ Affine.scale(DS, -DS) @ Affine.translate(*-ctr)
        polys = [Polygon(sec.apply(q)).buffer(0) for q in local]
        solid = unary_union(polys)
        cut, edge, ghost = P(), P(), P()
        for seg in hatch(solid, 5, deg=-45):
            cut.poly(seg)
        for g in polys:
            edge.shape(g)
        for q in opened:
            ghost.shape(Polygon(sec.apply(q)).exterior.difference(solid.buffer(3)))
        # streamlines turned up by the wing, stopping short of both flap positions
        x0, y0, x1, y1 = solid.bounds
        xs = np.linspace(BUB.x - BR - 10, BUB.x + BR + 10, 160)
        xc, lift = (x0 + x1) / 2 + 10, (y1 - y0) - 10
        disk = Point(BUB).buffer(BR, quad_segs=128)
        wake = unary_union([solid, *(Polygon(sec.apply(q)) for q in opened)]).buffer(7)
        for off in (-104, -64, 44, 82):
            ys = y1 - 12 + off - lift * (1 - abs(off) / 160) / (1 + np.exp(-(xs - xc) / 40))
            fine.shape(LineString(np.column_stack([xs, ys])).intersection(disk).difference(wake))
        pv = sec(PIVOT)
        le0, le1 = sec(REAR_WING[1][5]), sec(turn(REAR_WING[1][5]))
        a0 = math.degrees(math.atan2(le0[1] - pv.y, le0[0] - pv.x))
        a1 = math.degrees(math.atan2(le1[1] - pv.y, le1[0] - pv.x))
        swing = abs(Vec(*le0) - pv) + 14
        fine.arc(pv, swing, deg=(a0 + 3, a1 - 5))
        heads.arrowhead(
            pv + Vec(math.cos(math.radians(a1)), math.sin(math.radians(a1))) * swing,
            7,
            deg=a1 + 90,
            width=2.6,
        )

        # the call-out on the rear wing and its leader to detail A
        wc = m((3800, 805))
        u = (BUB - wc).unit()
        lips.M(wc + u * 62).L(BUB - u * BR).circle(BUB, BR)

        s.stroke(fine, UI, 1)
        s.stroke(wing, UI_HI, 1, join="round")
        s.stroke(outline, UI_HI, 1.5, join="round", cap="round")
        s.stroke(rings, UI_ALT, 1.25)
        s.stroke(lips, UI_ALT, 1)
        s.stroke(P().circle(wc, 62), UI_ALT, 1, dash=(6, 4))
        s.stroke(ghost, UI_ALT, 1, dash=(7, 4))
        s.fill(heads, UI_HI)
        for text, at in (
            (str(TOP_Z), (hx - 12, round(mid) - 8)),
            ("FIG. 1", (X0, GY + 140)),
            ("A", (round(BUB.x + BR * 0.72) + 8, round(BUB.y - BR * 0.72) - 24)),
            ("A", (round(wc.x + 62 * 0.72) + 6, round(wc.y - 62 * 0.72) - 22)),
        ):
            glyphs(s, text, UI_HI, at=at, font="8x16", px=1)
        s.stroke(cut, ACCENT, 0.9)
        s.stroke(edge, ACCENT, 1.2, join="round")
        s.fill(P().circle(pv, 3), ACCENT_HI)  # the flap's hinge line

"""A ground-effect race car as a patent-sheet side elevation in hairlines, with detail A hatching the rear wing's two NACA sections."""

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray
from shapely import LineString, Point, Polygon, unary_union

from walldye import ACCENT, ACCENT_HI, UI, UI_ALT, UI_HI, Canvas, P, Path, Vec, design
from walldye.geom import Affine, hatch, spline_points
from walldye.pixel import glyphs, text_width

# The figure is laid out on a 1920x1080 sheet and centred on wider screens.
SC, X0, GY = 220, 290, 730  # px per metre, front-wing tip, ground line
R_TYRE, AXLES = 0.36, (1.1, 4.7)  # metres
BUB, BR = Vec(1620, 300), 150  # detail A
FIG_CX = 985  # middle of the figure, from the ground line's start to detail A's rim

# Body lines in metres, x back from the front-wing tip and y up from the ground (2022-25 rules,
# traced against side-on F1-75 and W13 photos).
TOP = ((0.10, 0.165), (0.40, 0.25), (0.90, 0.38), (1.50, 0.52), (2.00, 0.62), (2.10, 0.66))
COVER = (
    (2.90, 0.73),
    (2.96, 0.80),
    (2.99, 0.91),
    (3.05, 0.97),
    (3.18, 0.99),
    (3.40, 0.96),
    (3.90, 0.84),
    (4.25, 0.74),
    (4.55, 0.61),
    (4.90, 0.50),
    (5.15, 0.455),
    (5.40, 0.44),
)
RIM = ((2.10, 0.66), (2.50, 0.69), (2.90, 0.73))  # cockpit rim
NOSE_UNDER = ((0.10, 0.11), (0.50, 0.15), (1.00, 0.19), (1.30, 0.20))
HALO = ((2.07, 0.655), (2.10, 0.78), (2.19, 0.85), (2.55, 0.875), (2.80, 0.85), (2.87, 0.75))
HELMET, VISOR = (2.57, 0.775), ((2.48, 0.80), (2.58, 0.815), (2.665, 0.80))
INLET = ((2.38, 0.63), (2.31, 0.61), (2.285, 0.55), (2.30, 0.49), (2.38, 0.465))
POD = ((2.38, 0.63), (2.80, 0.64), (3.30, 0.61), (3.90, 0.52), (4.30, 0.43))
UNDERCUT = ((2.38, 0.465), (2.47, 0.34), (2.70, 0.25), (3.30, 0.17), (3.95, 0.13))
SHOULDER = ((3.35, 0.83), (3.90, 0.73), (4.30, 0.63))
FLOOR = ((1.55, 0.20), (1.60, 0.10), (1.66, 0.05), (4.45, 0.05))
DIFFUSER = ((4.95, 0.10), (5.20, 0.20), (5.47, 0.33))
FPLATE = (
    (0.02, 0.02),
    (0.00, 0.06),
    (0.02, 0.12),
    (0.30, 0.15),
    (0.48, 0.22),
    (0.58, 0.32),
    (0.645, 0.325),
    (0.645, 0.02),
)
RPLATE_FRONT = (
    (5.36, 0.55),
    (5.27, 0.61),
    (5.22, 0.71),
    (5.205, 0.82),
    (5.24, 0.905),
    (5.34, 0.94),
    (5.50, 0.95),
)
RPLATE_BACK = ((5.60, 0.95), (5.63, 0.93), (5.63, 0.55))
PYLON = ((5.36, 0.44), (5.33, 0.60), (5.31, 0.80))
LENGTH, HEIGHT = 5.63, 0.99

# NACA sections: chord, camber, camber position, thickness, angle of attack (deg), leading edge.
# Front wing: mainplane and three flaps stepping up and back behind the endplate.
FRONT_WING = (
    (0.44, 0.05, 0.4, 0.08, 2, (0.03, 0.04)),
    (0.22, 0.05, 0.4, 0.10, 10, (0.39, 0.07)),
    (0.17, 0.05, 0.4, 0.10, 22, (0.47, 0.12)),
    (0.13, 0.05, 0.4, 0.11, 36, (0.52, 0.18)),
)
# Rear wing mainplane and DRS flap (the sections of detail A), then the two-element beam wing.
REAR_WING = (
    (0.25, 0.06, 0.40, 0.16, 8, (5.25, 0.79)),
    (0.115, 0.07, 0.35, 0.15, 30, (5.4825, 0.8325)),
    (0.14, 0.04, 0.4, 0.12, 4, (5.34, 0.40)),
    (0.09, 0.05, 0.4, 0.12, 22, (5.49, 0.425)),
)
# Detail A at unit chord; its scale puts the mainplane's leading edge at `SEC_AT`.
MAIN = (1.0, 0.06, 0.40, 0.16, 8, (0.0, 0.0))
FLAP = (0.45, 0.07, 0.35, 0.15, 30, (0.93, 0.17))
SEC_CHORD, SEC_AT = 186, BUB + (-0.62 * 186, 0.16 * 186)


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


def cross(d: Path, c: Vec, r: float) -> None:
    """A centre mark: two strokes of half-length `r` through `c`."""
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
    m = Affine.translate(X0, GY) @ Affine.scale(SC, -SC)  # metres, y up, to the sheet

    def curve(pts: ArrayLike, n: int = 14) -> NDArray[np.float64]:
        return spline_points(m.apply(pts), n)

    with s.group(transform=Affine.translate(round(s.w / 2 - FIG_CX), 0)):
        r = R_TYRE * SC
        hubs = [m((ax, R_TYRE)) for ax in AXLES]
        hidden = unary_union([Point(c).buffer(r + 5, quad_segs=64) for c in hubs])

        # Hidden-line work: body lines stop at the tyres, endplates and halo tube.
        front = Polygon(m.apply(FPLATE))
        rplate = np.concatenate([curve(RPLATE_FRONT, 8), m.apply(RPLATE_BACK)])
        rear = Polygon(rplate)
        helmet = Point(m(HELMET)).buffer(0.11 * SC, quad_segs=64)
        tube = LineString(curve(HALO)).buffer(3.2, cap_style="flat", join_style="round")
        cockpit = Polygon(
            np.concatenate([m.apply([(2.0, 0.0)]), curve(RIM), m.apply([(3.0, 0.0)])])
        )

        outline, fine, wing = P(), P(), P()
        outline.poly(m.apply(FPLATE), closed=True).poly(rplate, closed=True)
        outline.shape(LineString(curve(TOP)).difference(hidden).difference(front))
        outline.shape(LineString(curve(COVER)).difference(hidden).difference(rear))
        outline.shape(LineString(curve(RIM)).difference(tube))
        outline.shape(tube.exterior.difference(cockpit))
        outline.shape(LineString(curve(NOSE_UNDER)).difference(hidden).difference(front))
        outline.shape(LineString(m.apply(FLOOR)).difference(hidden))
        outline.shape(LineString(m.apply(DIFFUSER)).difference(hidden).difference(rear))
        outline.spline(m.apply(INLET))

        fine.M(200, GY).H(1600)  # ground line
        for pts in (POD, UNDERCUT, SHOULDER):
            fine.shape(LineString(curve(pts)).difference(hidden))
        fine.shape(LineString(m.apply(PYLON)).difference(rear))
        fine.shape(helmet.exterior.difference(cockpit).difference(tube))
        fine.shape(LineString(curve(VISOR, 6)).difference(tube))
        # floor fences under the inlet, and the floor-edge wing ahead of the undercut
        for i in range(4):
            x = 1.72 + 0.11 * i
            fine.spline(m.apply([(x, 0.05), (x + 0.03, 0.14), (x + 0.10, 0.19 - 0.012 * i)]))
        fine.poly(m.apply([(2.20, 0.09), (2.55, 0.105)]))
        fine.arc(hubs[0], r + 10, deg=(-96, -62))  # wake deflector over the front tyre
        for sec in (*FRONT_WING, *REAR_WING):
            wing.poly(m.apply(naca(*sec, n=24)), closed=True)

        # wheels: tyre, 18-inch rim and hub; the rim's inner lip shares the thinner leader stroke
        rings, lips = P(), P()
        for c in hubs:
            rings.circle(c, r).circle(c, 0.66 * r).circle(c, 0.14 * r)
            lips.circle(c, 0.61 * r)
            cross(fine, c, 16)
        cross(fine, m((3.05, 0.28)), 14)  # centre of gravity
        fine.circle(m((3.05, 0.28)), 5)

        # dimensions: wheelbase, overall length, height
        heads = P()
        dimension(s, fine, heads, hubs[0].x, hubs[1].x, GY + 58, "3600")
        dimension(s, fine, heads, X0, m((LENGTH, 0)).x, GY + 98, "5630")
        hx, htop = X0 - 60, m((0, HEIGHT)).y
        mid = (GY + htop) / 2
        fine.M(m((3.10, HEIGHT)).x - 6, htop).H(hx - 8).M(X0 - 8, GY).H(hx - 8)
        fine.M(hx, GY).V(mid + 22).M(hx, mid - 22).V(htop)
        heads.arrowhead((hx, htop), 7, deg=-90, width=2.6).arrowhead((hx, GY), 7, deg=90, width=2.6)

        # detail A: the rear wing's two sections enlarged 3.4 times, flow turned up by the wing
        sec = Affine.translate(*SEC_AT) @ Affine.scale(SEC_CHORD, -SEC_CHORD)
        polys = [Polygon(sec.apply(naca(*q))).buffer(0) for q in (MAIN, FLAP)]
        body = unary_union(polys)
        x0, y0, x1, y1 = body.bounds
        xs = np.linspace(BUB.x - BR - 10, BUB.x + BR + 10, 160)
        xc, lift = (x0 + x1) / 2 + 20, (y1 - y0) - 18
        disk, wake = Point(BUB).buffer(BR, quad_segs=128), body.buffer(6)
        for off in (-74, -38, 30, 64):
            ys = y1 - 12 + off - lift * (1 - abs(off) / 150) / (1 + np.exp(-(xs - xc) / 38))
            fine.shape(LineString(np.column_stack([xs, ys])).intersection(disk).difference(wake))
        cut, edge = P(), P()
        for seg in hatch(body, 5, deg=-45):
            cut.poly(seg)
        for g in polys:
            edge.shape(g)

        # the call-out on the rear wing and its leader to detail A
        wc = m((5.40, 0.84))
        u = (BUB - wc).unit()
        lips.M(wc + u * 30).L(BUB - u * BR).circle(BUB, BR)

        s.stroke(fine, UI, 1)
        s.stroke(wing, UI_HI, 1, join="round")
        s.stroke(outline, UI_HI, 1.5, join="round", cap="round")
        s.stroke(rings, UI_ALT, 1.25)
        s.stroke(lips, UI_ALT, 1)
        s.stroke(P().circle(wc, 30), UI_ALT, 1, dash=(6, 4))
        s.fill(heads, UI_HI)
        for text, at in (
            ("950", (hx - 12, round(mid) - 8)),
            ("FIG. 1", (X0, GY + 140)),
            ("A", (round(BUB.x + BR * 0.72) + 8, round(BUB.y - BR * 0.72) - 24)),
            ("A", (round(wc.x) + 28, round(wc.y) - 50)),
        ):
            glyphs(s, text, UI_HI, at=at, font="8x16", px=1)
        s.stroke(cut, ACCENT, 0.9)
        s.stroke(edge, ACCENT, 1.2, join="round")
        s.fill(P().circle(sec((0, 0)) - (1, 2), 3), ACCENT_HI)  # the leading edge

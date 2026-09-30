"""A Keplerian telescope as a paraxial ray diagram with hatched lenses."""

import math
from collections.abc import Sequence

from shapely import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_5,
    ACCENT_6,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Color,
    P,
    Params,
    Path,
    Ref,
    design,
    knob,
)
from walldye.geom import hatch

AY = 520  # principal axis
XO, FO, HO = 410, 720, 150  # objective: position, focal length, half-aperture
FE, HE = 260, 120  # eyepiece focal length, half-aperture
XF = XO + FO  # the shared focus
XE = XF + FE
XP = XE + FE * (FO + FE) / FO  # exit pupil, where the off-axis bundles cross again
TAIL = 100  # off-axis rays fade out over this distance past the exit pupil
THETA = 0.036  # off-axis stars' angle (tan)
HEIGHTS = (-136, -68, 0, 68, 136)
DASHDOT = (26, 7, 3, 7)

type Pts = list[tuple[float, float]]


def surface(x0: float, h: float, sag: float, n: int = 40) -> Pts:
    """Lens surface through (x0 + sag, AY ± h) bulging to x0 on the axis, flat when sag is 0;
    points run top to bottom."""
    r = (h * h + sag * sag) / (2 * abs(sag)) if sag else 0.0
    out: Pts = []
    for i in range(n + 1):
        y = -h + 2 * h * i / n
        dx = math.copysign(r - math.sqrt(r * r - y * y), sag) if sag else 0.0
        out.append((x0 + dx, AY + y))
    return out


def lens(front: Pts, back: Pts) -> Polygon:
    return Polygon(front + back[::-1])


def section(d: Path, glass: BaseGeometry, pitch: float, deg: float) -> None:
    """Section lines across `glass`, without the slivers under 1 unit at its corners."""
    for seg in hatch(glass, pitch, deg=deg):
        (x0, y0), (x1, y1) = seg.tolist()
        if math.hypot(x1 - x0, y1 - y0) > 1:
            d.poly(seg)


def trace(h: float, m: float, end: float) -> Pts:
    """Paraxial ray meeting the objective at height h (up = negative y) with slope m, through
    both thin lenses and out to x = end; screen points."""
    m1 = m - h / FO
    h2 = h + m1 * (XE - XO)
    m2 = m1 - h2 / FE
    pts = [(0, h - m * XO), (XO, h), (XE, h2), (end, h2 + m2 * (end - XE))]
    return [(x, AY - y) for x, y in pts]


def fade(s: Canvas, stops: Sequence[tuple[float, Color, float]]) -> Ref:
    """A horizontal gradient through (canvas x, color, opacity) stops."""
    x0, x1 = stops[0][0], stops[-1][0]
    return s.linear_gradient([((x - x0) / (x1 - x0), c, a) for x, c, a in stops], (x0, 0), (x1, 0))


class Drawing(Params):
    dimensions: bool = knob(default=True, doc="the focal-length dimensions")


@design(variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    # objective: crown biconvex cemented to a flint plano-concave; eyepiece: a biconvex singlet
    front, cement = surface(XO - 28, HO, 18), surface(XO + 14, HO, -14)
    crown, flint = lens(front, cement), lens(cement, surface(XO + 20, HO, 0))
    eye = lens(surface(XE - 20, HE, 16), surface(XE + 20, HE, -16))
    glass = unary_union([crown, flint, eye])

    hat = P()
    section(hat, crown, 9, -45)
    section(hat, flint, 5, 45)
    section(hat, eye, 9, -45)
    s.stroke(hat, UI, 1)

    s.stroke(P().M(0, AY).H(s.w).M(XF, AY - 120).V(AY + 120), UI_ALT, 1.2, dash=DASHDOT)
    stop = P()
    for sgn in (-1, 1):
        stop.M(XF, AY + sgn * 48).V(AY + sgn * 76)
    s.stroke(stop, UI_ALT, 2)

    off = P()
    for m in (-THETA, THETA):
        for h in HEIGHTS:
            off.shape(LineString(trace(h, m, XP + TAIL)).difference(glass))
    s.stroke(off, fade(s, [(XP, UI, 1), (XP + TAIL, UI, 0)]), 1.2)

    # the star's light is lit only between objective and eyepiece; it arrives and leaves dim
    star, heads = P(), P()
    for h in HEIGHTS:
        pts = trace(h, 0, XP)
        star.shape(LineString(pts).difference(glass))
        heads.arrowhead((207, pts[0][1]), 12, deg=0, width=4.5)
    lit = [(XO - 130, ACCENT_6, 1), (XO, ACCENT, 1), (XE, ACCENT, 1), (XP, ACCENT_6, 1)]
    s.stroke(star, fade(s, lit), 1.5)
    s.fill(heads, ACCENT_5)

    if s.params.dimensions:
        # focal-length dimensions below the axis
        dims, arrows = P(), P()
        yd = AY + 200
        for x, top in ((XO, AY + HO + 14), (XF, AY + 130), (XE, AY + HE + 14)):
            dims.M(x, top).V(yd + 14)
        for x0, x1 in ((XO, XF), (XF, XE)):
            dims.M(x0, yd).H(x1)
            arrows.arrowhead((x0, yd), 13, deg=180, width=4).arrowhead((x1, yd), 13, deg=0, width=4)
        s.stroke(dims, UI, 1.2)
        s.fill(arrows, UI_ALT)

    outline = P().shape(unary_union([crown, flint])).poly(cement).shape(eye)
    s.stroke(outline, UI_HI, 1.6, join="round")

    # the focus gets a tick cross, the exit pupil a single tick
    t = P().M(XF - 12, AY).H(XF + 12).M(XF, AY - 12).V(AY + 12).M(XP, AY - 64).V(AY + 64)
    s.stroke(t, UI_HI, 1.4)

"""A single-cylinder engine in drafted section at top dead center: ruled hatching on the cut parts, a stippled burn in the combustion chamber."""

import math

import numpy as np
import shapely
from shapely import LineString, Point, Polygon, box
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    BG,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    Rect,
    Vec,
    design,
    knob,
    polar,
)
from walldye.geom import Affine, bezier_points, hatch, poisson_disk

# The figure is drawn with the bore axis at x = 0 in a 1080-tall box, then placed by one
# transform that puts (0, MID) on the placement point.
MID = 540
YH = 380  # head face / gasket plane
BORE, WALL, FIN = 100, 24, 208  # half bore, liner wall, fin reach from the axis
DOME_H = 50
RC = (BORE**2 + DOME_H**2) / (2 * DOME_H)  # dome radius: the arc meets the bore at the gasket
DOME_C = YH - DOME_H + RC
DOME_HALF = math.degrees(math.asin(BORE / RC))  # half the dome's arc, in degrees
HEAD_TOP, HEAD_W = YH - 172, 190
YB = YH + 262  # barrel foot / crankcase flange
THROW, ROD, PIN_DROP = 80, 270, 62
CROWN_TDC = YH + 6
CKY = CROWN_TDC + PIN_DROP + ROD + THROW
CRANK = 0.0  # crank bearing; 0 is top dead center, the rod on the bore axis
VALVE = 24  # valve axes lean this many degrees either side of the bore axis
R_TOP = (DOME_C - HEAD_TOP) / math.cos(math.radians(VALVE))  # where a stem leaves the head
STEM = R_TOP + 83 - RC
# a valve, head at y = 0 and stem up the axis (-y)
POPPET = ((-27, 0), (27, 0), (22, -7), (6, -24), (6, -STEM), (-6, -STEM), (-6, -24), (-22, -7))
DASH = (10, 6)
DASHDOT = (26, 6, 3, 6)
PHANTOM = (22, 5, 4, 5, 4, 5)


def valve_axis(sgn: int) -> Affine:
    """Local frame of one valve: the axis runs up local -y from the dome center, and local +x
    points across it, clockwise of up."""
    return Affine.frame((0, DOME_C), deg=sgn * VALVE)


def along(sgn: int, r: float, side: float = 0.0) -> Vec:
    """The point `r` out along a valve axis from the dome center, `side` across it."""
    return valve_axis(sgn)((side, -r))


class Drawing(Params):
    dimensions: bool = knob(default=True, doc="the stroke and head-width dimensions")


@design(aspects="any", variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    # right of center on landscape screens; centered and larger on width-bound portrait ones
    at = s.pick(landscape=(0.6458, 0.5), portrait=(0.49, 0.53))
    k = 0.88 if s.landscape else 1.35
    place = Affine.translate(at.x, at.y) @ Affine.scale(k) @ Affine.translate(0, -MID)

    main = Vec(0, CKY)
    cp = polar(main, THROW, bearing=CRANK)
    small = Vec(0, cp.y - math.sqrt(ROD**2 - cp.x**2))  # gudgeon pin, on the bore axis
    crown = small.y - PIN_DROP

    # --- sectioned parts -------------------------------------------------
    dome = Point(0, DOME_C).buffer(RC, quad_segs=48)
    chamber = unary_union(
        [dome.intersection(box(-BORE, YH - DOME_H - 2, BORE, YH)), box(-BORE, YH, BORE, crown)]
    )

    voids = [box(-13, HEAD_TOP - 1, 13, YH - DOME_H + 4)]  # spark plug bore
    for sgn in (-1, 1):
        # port: up the valve axis, then sweeping out through the side of the head
        exit_ = Vec(sgn * (HEAD_W + 2), YH - 104)
        bend = bezier_points([along(sgn, RC - 4), along(sgn, RC + 70), exit_], 40)
        port = LineString([*bend.tolist(), exit_ + (sgn * 20, 0)])
        voids.append(port.buffer(21, cap_style="flat"))
        guide = LineString([along(sgn, RC + 20), along(sgn, R_TOP + 10)])
        voids.append(guide.buffer(6, cap_style="flat"))
    head = box(-HEAD_W, HEAD_TOP, HEAD_W, YH).difference(dome).difference(unary_union(voids))

    walls = []
    for sgn in (-1, 1):
        a, b = sorted((sgn * BORE, sgn * (BORE + WALL)))
        walls.append(box(a, YH, b, YB))
        r0 = BORE + WALL - 2
        for y in range(YH + 14, YB - 18, 25):
            fin = [(r0, y), (FIN, y + 2), (FIN, y + 8), (r0, y + 10)]
            walls.append(Polygon([(sgn * x, fy) for x, fy in fin]))
    barrel = unary_union(walls)

    outer = unary_union([Point(main).buffer(196, quad_segs=48), box(-168, YB, 168, CKY)])
    inner = unary_union(
        [
            Point(main).buffer(172, quad_segs=48),
            box(-144, YB + 22, 144, CKY),
            box(-BORE, YB - 1, BORE, YB + 30),
        ]
    )
    case = outer.difference(inner).intersection(box(-300, YB, 300, CKY + 300))

    piston = box(-BORE + 2, crown, BORE - 2, crown + 150).difference(
        box(-BORE + 14, crown + 24, BORE - 14, crown + 151)
    )
    for j in range(3):  # ring grooves
        y = crown + 10 + j * 13
        piston = piston.difference(box(-BORE + 1, y, -BORE + 9, y + 5))
        piston = piston.difference(box(BORE - 9, y, BORE - 1, y + 5))
    pins = unary_union([Point(small).buffer(19, quad_segs=24), Point(cp).buffer(30, quad_segs=24)])

    # --- behind the section plane: crank web, then the rod ----------------
    arc = [polar(main, 124, bearing=CRANK + 180 + a) for a in range(-76, 77, 2)]
    web = (
        unary_union([Polygon([*arc, main]), Point(cp).buffer(48, quad_segs=32)])
        .convex_hull.buffer(-14, quad_segs=16)
        .buffer(14, quad_segs=16)
    )
    u = (cp - small).unit()
    n = u.perp()
    shank = Polygon([small + n * 14, cp + n * 26, cp - n * 26, small - n * 14])
    rod = unary_union(
        [shank, Point(small).buffer(31, quad_segs=24), Point(cp).buffer(52, quad_segs=32)]
    )

    with s.group(transform=place, stroke_linejoin="round"):
        # center lines sit beneath everything so parts interrupt them
        cl = P()
        cl.M(0, HEAD_TOP - 170).V(CKY + 270)
        cl.M(-270, CKY).H(270)
        cl.M(-44, small.y).H(44)
        cl.M(cp.x - 44, cp.y).H(cp.x + 44).M(cp.x, cp.y - 44).V(cp.y + 44)
        cl.circle(main, THROW)
        for sgn in (-1, 1):
            cl.M(along(sgn, RC + 4)).L(along(sgn, R_TOP + 110))
        s.stroke(cl, UI_ALT, 1.3, dash=DASHDOT)

        s.path(P().shape(web), fill=BG, stroke=UI_HI, stroke_width=2)
        s.path(P().shape(rod), fill=BG, stroke=UI_HI, stroke_width=2)
        thin, hidden = P(), P()
        for sgn in (-1, 1):
            # rod I-beam flanges and the big-end cap joint
            thin.M(small + u * 36 + n * (6 * sgn)).L(cp - u * 58 + n * (12 * sgn))
            joint = cp + n * (40 * sgn)
            hidden.M(joint - u * 28).L(joint + u * 34)
            thin.M(cp + n * (31 * sgn)).L(cp + n * (52 * sgn))
            hidden.M(sgn * 158, HEAD_TOP + 10).V(YB + 16)  # head studs
        hidden.circle(main, 40)  # main journal

        s.fill(P().shape(piston), BG)
        # section lining, one pitch and direction per part
        lined = (
            (unary_union([head, case]), 6.5, 45),
            (barrel, 6.5, -45),
            (piston, 4.5, -45),
            (pins, 4.2, 45),
        )
        lining = P()
        for region, pitch, ang in lined:
            for seg in hatch(region, pitch, deg=ang):
                lining.poly(seg)
        s.stroke(lining, UI, 1.15)

        edge = P()
        for g in (head, barrel, case, piston, pins):
            edge.shape(g)
        s.stroke(hidden, UI_ALT, 1.5, dash=DASH)
        s.stroke(thin, UI_ALT, 1.5)
        s.stroke(edge, UI_HI, 2)
        gasket = P()
        for sgn in (-1, 1):
            a, b = sorted((sgn * BORE, sgn * HEAD_W))
            gasket.rect(a, YH - 1.8, b - a, 3.6)
        s.fill(gasket, UI_ALT)

        # valves (not sectioned), their springs on the head, and the spark plug
        vp, wire = P(), P()
        for sgn in (-1, 1):
            ax = valve_axis(sgn)
            vp.poly(ax.apply(np.asarray(POPPET) + (0, 1 - RC)), closed=True)
            # spring in section: two staggered columns of cut-wire circles, seat washer below,
            # cap above
            base, top = R_TOP + 13, R_TOP + 68
            for side, phase in ((-1, 0.0), (1, 0.5)):
                for i in range(5):
                    wire.circle(along(sgn, base + 8 + (i + phase) * 9, side * 16), 4.2)
            for rr, w, h in ((base, 24, 3), (top, 23, 6)):
                cap = [(-w, -rr), (w, -rr), (w - 3, -rr - h), (-w + 3, -rr - h)]
                vp.poly(ax.apply(cap), closed=True)
        plug = P()
        plug.M(-11, YH - DOME_H - 2).V(HEAD_TOP).M(11, YH - DOME_H - 2).V(HEAD_TOP)
        plug.M(-22, HEAD_TOP).V(HEAD_TOP - 26).H(22).V(HEAD_TOP).Z()
        plug.M(-13, HEAD_TOP - 26).L(-10, HEAD_TOP - 88).H(10).L(13, HEAD_TOP - 26)
        plug.M(-5, HEAD_TOP - 88).V(HEAD_TOP - 102).H(5).V(HEAD_TOP - 88)
        for j in range(1, 9):  # thread
            y = YH - DOME_H - 2 - j * (YH - DOME_H - 2 - HEAD_TOP) / 9
            plug.M(-11, y).L(-6, y - 4).M(11, y).L(6, y - 4)
        s.path(vp, fill=BG, stroke=UI_HI, stroke_width=1.8)
        s.path(wire, fill=UI, stroke=UI_HI, stroke_width=1.5)
        s.stroke(plug, UI_HI, 1.8)

        if s.params.dimensions:
            # dimensions: stroke on the right, head width across the top
            ext, dl, heads = P(), P(), P()
            xd, bdc = 300, CROWN_TDC + 2 * THROW
            for y in (CROWN_TDC, bdc):
                ext.M(FIN + 14, y).H(xd + 14)
            dl.M(xd, CROWN_TDC).V(bdc)
            heads.arrowhead((xd, CROWN_TDC), 13, bearing=0, width=4.2)
            heads.arrowhead((xd, bdc), 13, bearing=180, width=4.2)
            yd = HEAD_TOP - 132
            for sgn in (-1, 1):
                ext.M(sgn * HEAD_W, HEAD_TOP - 12).V(yd - 14)
                heads.arrowhead((sgn * HEAD_W, yd), 13, bearing=sgn * 90, width=4.2)
            dl.M(-HEAD_W, yd).H(HEAD_W)
            s.stroke(ext, UI, 1.3)
            s.stroke(dl, UI_ALT, 1.3)
            s.fill(heads, UI_ALT)

            # BDC phantom of the crown, so the stroke dimension's lower extension lands on something
            s.stroke(P().M(-BORE + 4, bdc).H(BORE - 4), UI_ALT, 1.5, dash=PHANTOM)

        # combustion chamber: one glow of stipple, dense at the plug tip and dying out at the
        # dome rim
        spark = Vec(0, YH - DOME_H + 6)
        x0, y0, x1, y1 = chamber.bounds
        rng = s.rng(5)
        pts = poisson_disk(Rect(x0, y0, x1 - x0, y1 - y0), 2.7, rng)
        inside = shapely.contains_xy(chamber.buffer(-3.5), pts[:, 0], pts[:, 1])
        with s.buckets((ACCENT_1, ACCENT), "fill") as glow:
            for (x, y), ok in zip(pts.tolist(), inside.tolist(), strict=True):
                if not ok:
                    continue
                d = math.hypot(x - spark.x, (y - spark.y) * 1.25)
                if rng.random() > 0.012 + 0.988 * math.exp(-((d / 30) ** 1.8)):
                    continue
                glow[int(rng.random() < math.exp(-d / 45))].circle((x, y), 1.4)
        # lit only along the dome; the band down to the crown stays plain liner
        rim = P().arc((0, DOME_C), RC, bearing=(-DOME_HALF, DOME_HALF))
        s.stroke(rim, ACCENT, 2.2, cap="round")

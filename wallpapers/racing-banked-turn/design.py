"""A drafted cross-section of a Daytona turn to scale, keyed to a plan of the oval, with one car's force triangle lit at its center of mass."""

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray
from shapely import Polygon

from walldye import ACCENT, BG, UI, UI_ALT, UI_HI, Canvas, P, Params, Path, Vec, design, knob
from walldye.geom import Affine, hatch, parts

# Section coordinates in feet: x across the track towards the outside wall, z up, from the
# toe of the banking.
BANK = math.radians(31)
WIDTH = 40.0  # racing surface up the slope, toe to barrier face
RUN, RISE = WIDTH * math.cos(BANK), WIDTH * math.sin(BANK)
T = np.array([math.cos(BANK), math.sin(BANK)])  # up the slope
N = np.array([-math.sin(BANK), math.cos(BANK)])  # the surface normal, leaning to the infield
APRON = 20.0  # published as 12 to 30 ft
INFIELD = 12.0  # grass shown inside the apron
GRASS = -0.4  # the infield sits a little below the paving
SLAB = 0.6
BAND = 4.0  # depth of ground hatched under grade
SAFER_D, SAFER_H, TUBES, TUBE = 2.0, 3.2, 4, 0.8
WALL_T, WALL_H, FOOT = 1.4, 4.2, 3.0
FENCE = 22.0
SHOULDER = 5.0  # top of the embankment shown behind the wall
X_IN = -APRON - INFIELD
X_WALL = RUN + SAFER_D
X_OUT = X_WALL + WALL_T + SHOULDER
LANE = 17.0  # the car's center, up the slope from the toe
CG_H = 1.5
# car in rear view, in feet across and up from the road: the right half of the body from the
# valance's middle round to the roof's, the rear window, the spoiler blade and a tire
BODY = ((0.0, 0.85), (3.2, 0.85), (3.25, 2.25), (3.1, 2.5), (2.55, 2.55), (2.05, 3.75))
BODY += ((1.7, 3.95), (0.0, 4.02))
GLASS = ((0.0, 2.85), (1.9, 2.85), (1.55, 3.45), (0.0, 3.5))
SPOILER = (2.75, 2.55, 3.0)  # half-width, bottom, top
TIRE = (2.05, 3.0, 1.2, 0.15)  # inner and outer face, height, corner radius
W_LEN = 12.0  # the weight arrow, in feet of the sheet
OFF = 19.0  # the width dimension's offset from the surface
ARC_R = 13.0  # the angle dimension's radius
DASHDOT = (22, 6, 3, 6)
# key plan: data/tri-oval.json is the oval's centerline in feet, in travel order, from the
# center of the first and second turns; the section cuts it along +x at CUT_X
CUT_X = 991.0
PLAN_X, PLAN_Y = (-4333.0, CUT_X), (-1615.0, 1010.0)  # the plan's extent
KP = 0.075  # key plan scale, px per foot, beside a 15 px per foot section
REACH, LEG = 32, 32  # the cutting plane either side of the track, and its arrows
GAP = 60  # between the cutting plane and the section's infield


def whole(length: float) -> float:
    """The longest run up to `length` that ends a DASHDOT line on a whole dash."""
    period, dash = sum(DASHDOT), DASHDOT[0]
    return length if length < dash else (length - dash) // period * period + dash


def ang(p: Vec, q: Vec) -> float:
    """Screen angle in degrees from `p` to `q`."""
    return math.degrees(math.atan2(q.y - p.y, q.x - p.x))


def box(x0: float, z0: float, x1: float, z1: float) -> list[tuple[float, float]]:
    """A rectangle's corners in section coordinates."""
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


class Drawing(Params):
    dimensions: bool = knob(
        default=True, doc="the banking angle, width and fence height dimensions"
    )


@design(aspects="any", variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    if s.landscape:
        # key plan and section side by side on the line of action, shrunk to fit if need be
        scaled = (PLAN_X[1] - PLAN_X[0]) * KP + (X_OUT + 0.7 - X_IN) * 15
        f = min(1.0, (s.w - 240 - REACH - GAP) / scaled)
        k, kp, x_in = 15 * f, KP * f, X_IN
        left = (s.w - scaled * f - REACH - GAP) / 2
        left += min(200.0, max(0.0, left - 140))  # wide screens: the pair sits right of center
        toe = Vec(
            round(left + (PLAN_X[1] - PLAN_X[0]) * kp + REACH + GAP - X_IN * k), round(s.h * 0.8)
        )
    else:
        # width-bound: the wall keeps its margin and the infield runs off the left edge; the
        # key plan stands above
        k, kp = 13.5, 0.1
        toe = Vec(round(s.w - 100 - (X_OUT + 0.7) * k), round(s.h * 0.75))
        x_in = -toe.x / k - 2
    m = Affine.translate(toe.x, toe.y) @ Affine.scale(k, -k)

    def pts(a: ArrayLike) -> NDArray[np.float64]:
        return m.apply(np.asarray(a, dtype=float))

    def at(p: ArrayLike) -> Vec:
        x, z = np.asarray(p, dtype=float).tolist()
        return m((x, z))

    def poly(g: Polygon) -> Polygon:
        return Polygon(pts(np.asarray(g.exterior.coords)))

    grade = [(x_in, GRASS), (-APRON, GRASS), (-APRON, 0.0), (0.0, 0.0), (RUN, RISE), (X_OUT, RISE)]
    under = [(x, z - BAND) for x, z in reversed(grade)]
    paved = [(-APRON, 0.0), (0.0, 0.0), (RUN, RISE), (X_WALL, RISE)]
    slab = Polygon(paved + [(x, z - SLAB) for x, z in reversed(paved)])
    wall = Polygon(
        box(X_WALL, RISE - FOOT, X_WALL + WALL_T, RISE + WALL_H)[:2]
        + [(X_WALL + WALL_T, RISE + WALL_H), (X_WALL, RISE + WALL_H)]
    )
    band = Polygon(grade + under).difference(slab).difference(wall)

    # ground under grade, ruled and left open at the bottom
    ruled = P()
    for g in parts(band):
        if isinstance(g, Polygon):
            for seg in hatch(poly(g), 12, deg=45):
                ruled.poly(seg)
    s.stroke(ruled, UI, 1.0)

    s.fill(P().poly(pts(np.asarray(slab.exterior.coords)), closed=True), UI)

    # the concrete wall cut through, the barrier of steel tubes on foam in front of it
    wall_px = poly(wall)
    s.path(P().shape(wall_px), fill=BG, stroke=UI_ALT, stroke_width=1.4)
    cut = P()
    for seg in hatch(wall_px.buffer(-2), 5, deg=-45):
        cut.poly(seg)
    s.stroke(cut, UI, 1.0)
    safer = P()
    th = SAFER_H / TUBES
    for i in range(TUBES):
        safer.poly(pts(box(RUN, RISE + i * th, RUN + TUBE, RISE + (i + 1) * th)), closed=True)
    safer.poly(pts(box(RUN + TUBE, RISE + 0.5, X_WALL, RISE + SAFER_H - 0.5)), closed=True)
    s.stroke(safer, UI_ALT, 1.2)

    # catch fence on the back of the wall; its cables cross the section as dots
    fx = X_WALL + WALL_T - 0.35
    f0, f1 = RISE + WALL_H, RISE + WALL_H + FENCE
    s.stroke(P().M(at((fx, f0))).L(at((fx, f1))), UI_ALT, 1.6)
    cables = P()
    for i in range(1, 6):
        cables.circle(at((fx, f0 + FENCE * (i - 0.4) / 5)), 2.4)
    s.fill(cables, UI_ALT)

    # grade line, and break lines where the section stops
    edge = P().poly(pts(grade[:5] + [(RUN, RISE), (X_WALL, RISE)]))
    edge.poly(pts([(X_WALL + WALL_T, RISE), (X_OUT, RISE)]))
    s.stroke(edge, UI_ALT, 2.0, join="round")
    brk = P()
    for x, z in [(X_OUT, RISE)] + [(X_IN, GRASS)] * s.landscape:
        zm = z - BAND / 2
        brk.poly(
            pts(
                [(x, z + 0.8), (x, zm + 0.9), (x - 0.7, zm + 0.3)]
                + [(x + 0.7, zm - 0.3), (x, zm - 0.9), (x, z - BAND - 0.8)]
            )
        )
    s.stroke(brk, UI, 1.2)

    # the car, square to the banking
    frame = Affine.translate(*(T * LANE)) @ Affine.rotate(rad=BANK)

    def car(a: ArrayLike) -> NDArray[np.float64]:
        return pts(frame.apply(np.asarray(a, dtype=float)))

    def mirrored(half: tuple[tuple[float, float], ...]) -> list[tuple[float, float]]:
        return [(-u, v) for u, v in reversed(half)] + list(half[1:-1])

    u0, u1, th, cr = TIRE
    tires = P()
    for x0, x1 in ((u0, u1), (-u1, -u0)):
        tire = Polygon(box(x0, 0.0, x1, th)).buffer(-cr).buffer(cr, quad_segs=4)
        tires.poly(car(np.asarray(tire.exterior.coords)), closed=True)
    body = P().poly(car(mirrored(BODY)), closed=True)
    sw, sb, st = SPOILER
    blade = P().poly(car(box(-sw, sb, sw, st)), closed=True)
    # each hides what is behind it; the window goes between the body and the blade
    for d in (tires, body):
        s.path(d, fill=BG, stroke=UI_HI, stroke_width=1.3, stroke_linejoin="round")
    s.fill(P().poly(car(mirrored(GLASS)), closed=True), UI)
    s.path(blade, fill=BG, stroke=UI_HI, stroke_width=1.3, stroke_linejoin="round")

    # force triangle at the center of mass: the normal force, the weight, and their resultant
    cg = T * LANE + N * CG_H
    top = cg + N * (W_LEN / math.cos(BANK))
    tip = top + (0.0, -W_LEN)
    g, a, b = at(cg), at(top), at(tip)
    legs, result = P().M(g).L(a).L(b), P().M(g).L(b)
    s.stroke(P().M(g).L(a).L(b).M(g).L(b), BG, 5, cap="round", join="round")
    s.stroke(legs, ACCENT, 1.6, join="round")
    s.stroke(result, ACCENT, 2.4)
    heads = P()
    heads.arrowhead(a, 12, deg=ang(g, a), width=4)
    heads.arrowhead(b, 12, deg=ang(a, b), width=4)
    heads.arrowhead(b, 12, deg=ang(g, b), width=4)
    cg_mark(heads, g, 6)
    s.fill(heads, ACCENT)
    s.stroke(P().circle(g, 6), ACCENT, 1.4)

    # the line of action runs on to the turn's center in the key plan beside the section, or
    # off the edge when the plan stands above it
    if s.landscape:
        center = Vec(at((x_in, 0)).x - GAP - REACH - CUT_X * kp, b.y)
        run = b.x - 12 - (center.x + CUT_X * kp + REACH + 6)
        stretch = run / whole(run)  # a few percent, so the line ends on a dash at the cut
        action = P().M(b.x - 12, b.y).H(b.x - 12 - run)
        s.stroke(action, UI_ALT, 1.2, dash=[d * stretch for d in DASHDOT])
    else:
        mid = Vec(s.w * 0.45, at((fx, f1)).y - 130)
        center = mid + Vec(-sum(PLAN_X) / 2, sum(PLAN_Y) / 2) * kp
        s.stroke(P().M(b.x - 12, b.y).H(0), UI_ALT, 1.2, dash=DASHDOT)
    inner = center.x + CUT_X * kp - REACH - 6
    if inner - center.x - 12 >= DASHDOT[0]:
        stub = P().M(inner, center.y).H(inner - whole(inner - center.x - 12))
        s.stroke(stub, UI_ALT, 1.2, dash=DASHDOT)
    key_plan(s, s.data("tri-oval.json"), center, kp)

    if s.params.dimensions:
        # dimensions: the banking angle at the top, the width up the slope, the fence height
        ext, dims, arrows = P(), P(), P()
        crest = at((RUN, RISE))
        ext.M(at((RUN - 1.2, RISE))).L(at((RUN - ARC_R - 2.5, RISE)))
        r = ARC_R * k
        dims.arc(crest, r, deg=(149, 180))
        for deg, turn in ((180, 90), (149, -90)):
            end = crest + Vec(math.cos(math.radians(deg)), math.sin(math.radians(deg))) * r
            arrows.arrowhead(end, 12, deg=deg + turn, width=3.6)
        lo, hi = np.zeros(2), np.array([RUN, RISE])
        for p in (lo, hi):
            ext.M(at(p + N * 1.5)).L(at(p + N * (OFF + 1.5)))
        da, db = at(lo + N * OFF), at(hi + N * OFF)
        dims.M(da).L(db)
        arrows.arrowhead(da, 12, deg=ang(db, da), width=3.6)
        arrows.arrowhead(db, 12, deg=ang(da, db), width=3.6)
        xf = fx + 4.5
        for z in (f0, f1):
            ext.M(at((fx + 1.2, z))).L(at((xf + 1.5, z)))
        fa, fb = at((xf, f0)), at((xf, f1))
        dims.M(fa).L(fb)
        arrows.arrowhead(fa, 12, deg=90, width=3.6).arrowhead(fb, 12, deg=-90, width=3.6)
        s.stroke(ext, UI, 1.2)
        s.stroke(dims, UI_ALT, 1.2)
        s.fill(arrows, UI_ALT)


def key_plan(s: Canvas, loop: list[list[float]], center: Vec, kp: float) -> None:
    """The oval in plan at `kp` px per foot, with the center of the cut turn at `center`: the
    track as a fixed-width band, the cutting plane across the turn with arrows looking along the direction of
    travel, and a center mark."""
    mp = Affine.translate(*center) @ Affine.scale(kp, -kp)
    line = np.asarray(loop, dtype=float)
    for _ in range(2):  # Chaikin corner cutting evens out the tracing
        nxt = np.roll(line, -1, axis=0)
        line = np.stack([0.75 * line + 0.25 * nxt, 0.25 * line + 0.75 * nxt], axis=1).reshape(-1, 2)
    track = P().poly(mp.apply(line), closed=True)
    s.stroke(track, UI, 8, join="round")  # widened well past scale so the loop reads as a track
    cross = mp((CUT_X, 0.0))
    ends = [Vec(cross.x - REACH, cross.y), Vec(cross.x + REACH, cross.y)]
    plane, heads = P(), P()
    for e in ends:
        plane.M(e.x, e.y + 1).V(e.y - LEG + 6)
        heads.arrowhead((e.x, e.y - LEG), 16, deg=-90, width=5)
    plane.M(ends[0]).L(ends[1])
    s.stroke(plane, UI_HI, 2.2, dash=(14, 4, 4, 4))
    s.fill(heads, UI_HI)
    mark = P().M(center.x - 9, center.y).H(center.x + 9).M(center.x, center.y - 9).V(center.y + 9)
    s.stroke(mark, UI_ALT, 1.4)


def cg_mark(d: Path, c: Vec, r: float) -> None:
    """The center-of-mass symbol's two filled quadrants, upper left and lower right."""
    d.M(c).L(c.x - r, c.y).A(r, r, 0, 0, 1, c.x, c.y - r).Z()
    d.M(c).L(c.x + r, c.y).A(r, r, 0, 0, 1, c.x, c.y + r).Z()

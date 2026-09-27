"""Patent figure of a lamp where only the filament glows: shapely-clipped ruled shading, placed as one figure group."""

import math

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import substring

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, UI_HI, H, P, W, accent_ramp, poisson_disk, rng

ASPECTS = ["any"]

# The figure is drawn once in a 1080-tall reference box with the lamp axis at x=0; one transform
# places it at 0.615 of a landscape canvas's width, or centred (and larger, since a phone is
# width-bound) in portrait.
U = min(W, H) / 1080
FX, FY, K = (0.615 * W, H / 2, U) if W >= H else (W / 2, 0.54 * H, 1.35 * U)
TILT = 0.2  # ellipse squash: we look slightly down on the lamp
# right half of the glass profile, crown to neck (dx, y)
PROFILE = [(0, 196), (72, 206), (132, 238), (172, 292), (188, 358), (182, 428), (158, 494), (122, 556), (94, 604), (80, 648), (77, 684)]
NECK, THREAD_TOP, THREAD_R, AMP, PITCH, TURNS = 684, 688, 76, 6, 25, 4


def catmull(points, n=12):
    """Points along a Catmull-Rom spline through `points` (shapely needs vertices, not Béziers)."""
    p = [points[0], *points, points[-1]]
    out = []
    for p0, p1, p2, p3 in zip(p, p[1:], p[2:], p[3:]):
        for t in (k / n for k in range(n)):
            out.append(tuple(0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t**3) for a, b, c, d in zip(p0, p1, p2, p3)))
    return out + [points[-1]]


def emit(d, geom):
    for g in getattr(geom, "geoms", [geom]):
        if isinstance(g, LineString) and not g.is_empty:
            d.poly(g.coords)
        elif isinstance(g, Polygon):
            d.poly(g.exterior.coords, closed=True)


def rules(lo, hi, count):
    """`count` offsets in (lo, hi) with density growing as x³, so ruling tightens towards the rim."""
    return [(lo**4 + k / (count + 1) * (hi**4 - lo**4)) ** 0.25 for k in range(1, count + 1)]


def hatch(d, xs, y0, y1, shape):
    for x in xs:
        emit(d, LineString([(x, y0), (x, y1)]).intersection(shape))


def ell(cy, r, a0=0.0, a1=math.pi, n=48, dy=0.0):
    """Arc of a horizontal circle seen from above; angles in (0, pi) are the front half."""
    return [(r * math.cos(a0 + (a1 - a0) * i / n), cy + TILT * r * math.sin(a0 + (a1 - a0) * i / n) + dy * i / n) for i in range(n + 1)]


def thread_y(q):
    return THREAD_TOP + q * PITCH / 4  # q = quarter-turns below the shell top


def draw(s):
    # one spline across the whole profile keeps the crown tangent horizontal
    glass_line = catmull([(-x, y) for x, y in reversed(PROFILE)] + PROFILE[1:])
    glass = Polygon(glass_line + ell(NECK, 77)[1:-1])
    inner = glass.buffer(-7)
    edge, ruled, fine, crests, dense, clamps, stip = (P() for _ in range(7))
    edge.poly(glass_line).poly(ell(NECK, 77)).M(-9, 197).Q(-5, 186, 0, 176).Q(5, 186, 9, 197)  # + exhaust tip
    hatch(ruled, rules(70, 186, 15), 150, NECK, inner)  # shadow side of the glass

    # glass stem, lead-in wires and their clamps
    edge.smooth([(-60, NECK - 2), (-44, 640), (-20, 596), (-16, 520), (16, 520), (20, 596), (44, 640), (60, NECK - 2)], tension=0.6)
    edge.M(-16, 520).Q(0, 512, 16, 520)
    for sg in (-1, 1):
        fine.M(sg * 8, NECK + 4).V(530).L(sg * 22, 486)
        clamps.M(sg * 22 - 3.5, 486).H(sg * 22 + 3.5).V(474).H(sg * 22 - 3.5).Z()

    # Edison screw: sine silhouettes ending on thread roots (right one half a turn lower), joined by front crests
    sil = [[(sg * THREAD_R - AMP * math.sin(math.pi / 2 * i / 12), thread_y(i / 12)) for i in range(12 * (4 * TURNS + sg) + 1)] for sg in (-1, 1)]
    edge.poly(sil[0]).poly(sil[1])
    for k in range(TURNS):
        crests.poly(ell(thread_y(4 * k + 1), THREAD_R + AMP, math.pi, 0, 60, dy=PITCH / 2))
    foot = ell(thread_y(4 * TURNS - 1), THREAD_R - AMP, math.pi, 0, 60, dy=PITCH / 2)
    edge.poly(foot)
    shell = Polygon(sil[0] + foot[1:-1] + sil[1][::-1] + ell(THREAD_TOP, THREAD_R)[1:-1])
    hatch(ruled, rules(26, THREAD_R - AMP - 4, 8), THREAD_TOP, THREAD_TOP + 200, shell.buffer(-3))

    # insulator in patent solid shading: dense ruling over a filled base
    ins_y = thread_y(4 * TURNS + 1) + 24
    ins = Polygon(foot + ell(ins_y, 52))
    hatch(dense, [-70 + 2.6 * i for i in range(54)], ins_y - 60, ins_y + 30, ins.buffer(-2))
    lip = ins_y + TILT * math.sqrt(52**2 - 22**2)
    edge.poly([foot[-1], *ell(ins_y, 52), foot[0]])
    edge.M(-22, lip).V(ins_y + 16).poly(ell(ins_y + 16, 22, math.pi, 0)).V(lip)

    # patent shade line: the lower-right edge carries a tapered extra weight
    arc = [p for p in glass_line if p[0] > 0 and 300 <= p[1] <= 640]
    swell = [(x + 2.4 * math.sin(math.pi * i / (len(arc) - 1)) ** 0.8, y) for i, (x, y) in enumerate(arc)]

    # stipple hugging the lit left rim, densest lower-left, fading past the crown and bottom-right
    r = rng(11)
    band = glass.buffer(-6).difference(glass.buffer(-30))
    x0, y0, x1, y1 = glass.bounds
    for x, y in poisson_disk(r, x1 - x0, y1 - y0, 4.2, x0=x0, y0=y0):
        pt = Point(x, y)
        if y > NECK - 14 or not band.contains(pt):
            continue
        near = 1 - (glass.exterior.distance(pt) - 6) / 24
        reach = max(0.0, math.cos(math.atan2(y - 420, x) - 2.3)) ** 0.7
        if r.random() < near**1.6 * reach:
            stip.M(x - 1.2, y).A(1.2, 1.2, 0, 1, 0, x + 1.2, y).A(1.2, 1.2, 0, 1, 0, x - 1.2, y)

    # filament: a horseshoe loop; the glow is offset rings that stop higher up and dissolve into dashes
    fil = [(-22, 478), (-30, 430), (-44, 372), (-50, 316), (-34, 272), (0, 258), (34, 272), (50, 316), (44, 372), (30, 430), (22, 478)]
    loop = Polygon(catmull(fil, 16))
    tones = accent_ramp(12)
    halos = []
    for off, cut, k in ((13, 452, 8), (27, 414, 6), (41, 376, 4)):
        ring = loop.buffer(off, quad_segs=24).exterior.intersection(box(-300, 0, 300, cut)).intersection(inner)
        solid, taper = P(), P()
        for g in getattr(ring, "geoms", [ring]):
            if isinstance(g, LineString) and not g.is_empty:
                L = g.length
                emit(solid, substring(g, 40, L - 40))
                for a, b in ((22, 34), (10, 17), (2, 5)):
                    emit(taper, substring(g, a, b))
                    emit(taper, substring(g, L - b, L - a))
        halos.append((solid, taper, tones[k], tones[k - 1]))

    # leaders: one gentle bow from each part to a ring marker in two tidy columns
    lead, rings, mr = P(), P(), 7
    for (sx, sy), (ex, ey) in (((183, 336), (280, 300)), ((82, thread_y(11)), (280, 800)), ((-25, 452), (-280, 404)), ((-37, 628), (-280, 668))):
        dx, dy, bow = ex - sx, ey - sy, math.copysign(0.12, ex - sx)
        tx = ex - math.copysign(mr, dx)
        lead.M(sx, sy).Q((sx + tx) / 2 - dy * bow, (sy + ey) / 2 + dx * bow * 0.5, tx, ey)
        rings.M(ex + mr, ey).A(mr, mr, 0, 1, 1, ex - mr, ey).A(mr, mr, 0, 1, 1, ex + mr, ey)

    place = f"translate({FX:.1f} {FY - 540 * K:.1f}) scale({K:.4f})"
    with s.g(transform=place, fill="none", stroke_linecap="round", stroke_linejoin="round"):
        s.path(P().poly(ins.exterior.coords, closed=True), fill=BG_ALT)
        s.path(dense, stroke=UI, stroke_width=1.2)
        s.path(ruled, stroke=UI_ALT, stroke_width=1.2)
        s.path(stip, fill=UI_ALT)
        for solid, taper, c, c2 in halos:
            s.path(solid, stroke=c, stroke_width=1.3)
            s.path(taper, stroke=c2, stroke_width=1.3)
        s.path(crests, stroke=UI_HI, stroke_width=1.6)
        s.path(fine, stroke=UI_HI, stroke_width=1.3)
        s.path(edge, stroke=UI_HI, stroke_width=1.6)
        s.path(P().poly(arc + swell[::-1], closed=True), fill=UI_HI)
        s.path(clamps, fill=BG, stroke=UI_HI, stroke_width=1.3)
        s.path(P().smooth(fil), stroke=ACCENT, stroke_width=2.6)
        s.path(lead, stroke=UI_ALT, stroke_width=1.3)
        s.path(rings, stroke=UI_HI, stroke_width=1.4)
        s.path(P().M(-56, 914).H(56), stroke=UI_ALT, stroke_width=2)

"""A patent figure of a lamp where only the filament glows: shapely-clipped ruled shading, placed as one transformed group."""

import math

from shapely import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import substring

from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Path,
    Rect,
    design,
    ladder,
)
from walldye.geom import Affine, parts, poisson_disk, spline_points

# The figure is drawn in a 1080-tall box with the lamp axis at x = 0, then placed by one
# transform.
TILT = 0.2  # ellipse squash: we look slightly down on the lamp
# right half of the glass profile, crown to neck (dx, y)
PROFILE = (
    (0, 196),
    (72, 206),
    (132, 238),
    (172, 292),
    (188, 358),
    (182, 428),
    (158, 494),
    (122, 556),
    (94, 604),
    (80, 648),
    (77, 684),
)
NECK, THREAD_TOP, THREAD_R, AMP, PITCH, TURNS = 684, 688, 76, 6, 25, 4
# the filament: a horseshoe loop
FILAMENT = (
    (-22, 478),
    (-30, 430),
    (-44, 372),
    (-50, 316),
    (-34, 272),
    (0, 258),
    (34, 272),
    (50, 316),
    (44, 372),
    (30, 430),
    (22, 478),
)
# glass stem, from one lead-in wire's foot round to the other's
STEM = (
    (-60, NECK - 2),
    (-44, 640),
    (-20, 596),
    (-16, 520),
    (16, 520),
    (20, 596),
    (44, 640),
    (60, NECK - 2),
)
GLOW = ladder((BG, ACCENT_4, ACCENT), 12)

type Pts = list[tuple[float, float]]


def rules(lo: float, hi: float, count: int) -> list[float]:
    """`count` offsets in (lo, hi) with density growing as x³, so ruling tightens to the rim."""
    return [(lo**4 + k / (count + 1) * (hi**4 - lo**4)) ** 0.25 for k in range(1, count + 1)]


def hatch(d: Path, xs: list[float], y0: float, y1: float, shape: BaseGeometry) -> None:
    """Vertical rules at `xs` from y0 to y1, clipped to `shape`."""
    for x in xs:
        d.shape(LineString([(x, y0), (x, y1)]).intersection(shape))


def ell(
    cy: float, r: float, a0: float = 0.0, a1: float = math.pi, n: int = 48, dy: float = 0.0
) -> Pts:
    """An arc of a horizontal circle seen from above, `dy` lower at its end; angles in
    (0, pi) are the front half."""
    return [
        (
            r * math.cos(a0 + (a1 - a0) * i / n),
            cy + TILT * r * math.sin(a0 + (a1 - a0) * i / n) + dy * i / n,
        )
        for i in range(n + 1)
    ]


def thread_y(q: float) -> float:
    return THREAD_TOP + q * PITCH / 4  # q = quarter-turns below the shell top


# leaders: from a part to its ring marker, the markers in two tidy columns
LEADERS = (
    ((183, 336), (280, 300)),
    ((82, thread_y(11)), (280, 800)),
    ((-25, 452), (-280, 404)),
    ((-37, 628), (-280, 668)),
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # 0.615 of a landscape canvas's width; centred, and larger since a phone is width-bound,
    # in portrait
    at = s.pick(landscape=(0.615, 0.5), portrait=(0.5, 0.54))
    k = 1.0 if s.landscape else 1.35
    place = Affine.translate(at.x, at.y - 540 * k) @ Affine.scale(k)

    # one spline across the whole profile keeps the crown tangent horizontal
    outline = [(-x, y) for x, y in reversed(PROFILE)] + list(PROFILE[1:])
    glass_line: Pts = spline_points(outline, 12).tolist()
    glass = Polygon(glass_line + ell(NECK, 77)[1:-1])
    inner = glass.buffer(-7)
    edge, ruled, fine, crests, dense, clamps, stip = (P() for _ in range(7))
    edge.poly(glass_line).poly(ell(NECK, 77))
    edge.M(-9, 197).Q(-5, 186, 0, 176).Q(5, 186, 9, 197)  # the exhaust tip
    hatch(ruled, rules(70, 186, 15), 150, NECK, inner)  # shadow side of the glass

    # glass stem, lead-in wires and their clamps
    edge.spline(STEM, tension=0.6).M(-16, 520).Q(0, 512, 16, 520)
    for sg in (-1, 1):
        fine.M(sg * 8, NECK + 4).V(530).L(sg * 22, 486)
        clamps.rect(sg * 22 - 3.5, 474, 7, 12)

    # Edison screw: sine silhouettes ending on thread roots (the right one half a turn lower),
    # joined by front crests
    sil = [
        [
            (sg * THREAD_R - AMP * math.sin(math.pi / 2 * i / 12), thread_y(i / 12))
            for i in range(12 * (4 * TURNS + sg) + 1)
        ]
        for sg in (-1, 1)
    ]
    edge.poly(sil[0]).poly(sil[1])
    for t in range(TURNS):
        crests.poly(ell(thread_y(4 * t + 1), THREAD_R + AMP, math.pi, 0, 60, dy=PITCH / 2))
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
    swell = [
        (x + 2.4 * math.sin(math.pi * i / (len(arc) - 1)) ** 0.8, y) for i, (x, y) in enumerate(arc)
    ]

    # stipple hugging the lit left rim, densest lower-left, fading past the crown and bottom-right
    rng = s.rng(11)
    band = glass.buffer(-6).difference(glass.buffer(-30))
    x0, y0, x1, y1 = glass.bounds
    for x, y in poisson_disk(Rect(x0, y0, x1 - x0, y1 - y0), 4.2, rng).tolist():
        pt = Point(x, y)
        if y > NECK - 14 or not band.contains(pt):
            continue
        near = 1 - (glass.exterior.distance(pt) - 6) / 24
        reach = max(0.0, math.cos(math.atan2(y - 420, x) - 2.3)) ** 0.7
        if rng.random() < near**1.6 * reach:
            stip.circle((x, y), 1.2)

    # the glow: offset rings round the filament that stop higher up and dissolve into dashes
    loop = Polygon(spline_points(FILAMENT, 16).tolist())
    halos: list[tuple[Path, Path, int]] = []
    for off, cut, tone in ((13, 452, 8), (27, 414, 6), (41, 376, 4)):
        ring = loop.buffer(off, quad_segs=24).exterior.intersection(box(-300, 0, 300, cut))
        solid, taper = P(), P()
        for g in parts(ring.intersection(inner)):
            if isinstance(g, LineString):
                n = g.length
                solid.shape(substring(g, 40, n - 40))
                for a, b in ((22, 34), (10, 17), (2, 5)):
                    taper.shape(substring(g, a, b)).shape(substring(g, n - b, n - a))
        halos.append((solid, taper, tone))

    # leaders: one gentle bow from each part to its ring marker
    lead, markers, mr = P(), P(), 7
    for (sx, sy), (ex, ey) in LEADERS:
        dx, dy, bow = ex - sx, ey - sy, math.copysign(0.12, ex - sx)
        tx = ex - math.copysign(mr, dx)
        lead.M(sx, sy).Q((sx + tx) / 2 - dy * bow, (sy + ey) / 2 + dx * bow * 0.5, tx, ey)
        markers.circle((ex, ey), mr)

    with s.group(transform=place, stroke_linecap="round", stroke_linejoin="round"):
        s.fill(P().shape(ins), BG_ALT)
        s.stroke(dense, UI, 1.2)
        s.stroke(ruled, UI_ALT, 1.2)
        s.fill(stip, UI_ALT)
        for solid, taper, tone in halos:
            s.stroke(solid, GLOW[tone], 1.3)
            s.stroke(taper, GLOW[tone - 1], 1.3)
        s.stroke(crests, UI_HI, 1.6)
        s.stroke(fine, UI_HI, 1.3)
        s.stroke(edge, UI_HI, 1.6)
        s.fill(P().poly(arc + swell[::-1], closed=True), UI_HI)
        s.path(clamps, fill=BG, stroke=UI_HI, stroke_width=1.3)
        s.stroke(P().spline(FILAMENT), ACCENT, 2.6)
        s.stroke(lead, UI_ALT, 1.3)
        s.stroke(markers, UI_HI, 1.4)
        s.stroke(P().M(-56, 914).H(56), UI_ALT, 2)

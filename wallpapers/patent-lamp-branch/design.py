"""Patent figure of an incandescent lamp in ruled shading and rim stipple, drawn in its own units
and placed on any screen by one transform; only the filament glows."""

import math

import numpy as np
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
    Vec,
    design,
    ladder,
    polar,
)
from walldye.geom import Affine, hatch, parts, poisson_disk, spline_points

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
# glow rings round the filament: offset, the height each stops at, and its GLOW rung
HALOS = ((13, 452, 8), (27, 414, 6), (41, 376, 4))
GLOW = ladder((BG, ACCENT_4, ACCENT), 12)
# the stipple gathers on the side of the glass facing LIT, seen from the bulb's middle
HUB, LIT = Vec(0, 420), polar((0, 0), 1, rad=2.3)
MARK_R = 7

type Pts = list[tuple[float, float]]


def tightening(lo: float, hi: float, count: int) -> list[float]:
    """`count` offsets in (lo, hi) with density growing as x³, so ruling tightens to the rim."""
    return [(lo**4 + k / (count + 1) * (hi**4 - lo**4)) ** 0.25 for k in range(1, count + 1)]


def rule(d: Path, xs: list[float], y0: float, y1: float, region: BaseGeometry) -> None:
    """Vertical rules at `xs` from `y0` to `y1`, clipped to `region`."""
    for x in xs:
        d.shape(LineString([(x, y0), (x, y1)]).intersection(region))


def ell(
    cy: float, r: float, a0: float = 0.0, a1: float = math.pi, n: int = 48, dy: float = 0.0
) -> Pts:
    """An arc of a horizontal circle of radius `r` seen from above, sinking by `dy` along its
    length; angles in (0, pi) are the front half."""
    return [
        (
            r * math.cos(a0 + (a1 - a0) * i / n),
            cy + TILT * r * math.sin(a0 + (a1 - a0) * i / n) + dy * i / n,
        )
        for i in range(n + 1)
    ]


def thread_y(q: float) -> float:
    """y of the screw silhouette `q` quarter-turns below the shell top."""
    return THREAD_TOP + q * PITCH / 4


# leaders: from a part to its ring marker, the markers in two tidy columns
LEADERS = (
    ((183, 336), (280, 300)),  # glass
    ((82, thread_y(11)), (280, 800)),  # screw base
    ((-25, 452), (-280, 404)),  # filament
    ((-37, 628), (-280, 668)),  # stem
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
    glass_line = spline_points(outline, 12)
    glass = Polygon(np.vstack([glass_line, ell(NECK, 77)[1:-1]]))
    inner = glass.buffer(-7)
    edge, ruled, fine, crests, dense, clamps, stip = (P() for _ in range(7))
    edge.poly(glass_line).poly(ell(NECK, 77))
    edge.M(-9, 197).Q(-5, 186, 0, 176).Q(5, 186, 9, 197)  # the exhaust tip
    rule(ruled, tightening(70, 186, 15), 150, NECK, inner)  # shadow side of the glass

    # glass stem, lead-in wires and their clamps
    edge.spline(STEM, tension=0.6).M(-16, 520).Q(0, 512, 16, 520)
    for sg in (-1, 1):
        fine.M(sg * 8, NECK + 4).V(530).L(sg * 22, 486)
        clamps.rect(sg * 22 - 3.5, 474, 7, 12)

    # Edison screw: sine silhouettes ending on thread roots (the right one half a turn lower),
    # joined by front crests
    sil_l, sil_r = (
        [
            (sg * THREAD_R - AMP * math.sin(math.pi / 2 * i / 12), thread_y(i / 12))
            for i in range(12 * (4 * TURNS + sg) + 1)
        ]
        for sg in (-1, 1)
    )
    edge.poly(sil_l).poly(sil_r)
    for t in range(TURNS):
        crests.poly(ell(thread_y(4 * t + 1), THREAD_R + AMP, math.pi, 0, 60, dy=PITCH / 2))
    foot = ell(thread_y(4 * TURNS - 1), THREAD_R - AMP, math.pi, 0, 60, dy=PITCH / 2)
    edge.poly(foot)
    shell = Polygon(sil_l + foot[1:-1] + sil_r[::-1] + ell(THREAD_TOP, THREAD_R)[1:-1])
    xs = tightening(26, THREAD_R - AMP - 4, 8)
    rule(ruled, xs, THREAD_TOP, THREAD_TOP + 200, shell.buffer(-3))

    # insulator in patent solid shading: dense ruling over a filled base
    ins_y = thread_y(4 * TURNS + 1) + 24
    ins = Polygon(foot + ell(ins_y, 52))
    for seg in hatch(ins.buffer(-2), 2.6, deg=90):
        dense.poly(seg)
    lip = ins_y + TILT * math.sqrt(52**2 - 22**2)
    edge.poly([foot[-1], *ell(ins_y, 52), foot[0]])
    edge.M(-22, lip).V(ins_y + 16).poly(ell(ins_y + 16, 22, math.pi, 0)).V(lip)

    # patent shade line: the lower-right edge carries a tapered extra weight
    x, y = glass_line[:, 0], glass_line[:, 1]
    arc = glass_line[(x > 0) & (y >= 300) & (y <= 640)]
    u = np.linspace(0, 1, len(arc))
    swell = arc + np.column_stack([2.4 * np.sin(np.pi * u) ** 0.8, np.zeros_like(u)])
    shade = P().poly(np.vstack([arc, swell[::-1]]), closed=True)

    # stipple hugging the lit left rim, densest lower-left, fading past the crown and bottom-right
    rng = s.rng(11)
    band = glass.buffer(-6).difference(glass.buffer(-30))
    x0, y0, x1, y1 = glass.bounds
    for px, py in poisson_disk(Rect(x0, y0, x1 - x0, y1 - y0), 4.2, rng).tolist():
        pt = Point(px, py)
        if py > NECK - 14 or not band.contains(pt):
            continue
        near = 1 - (glass.exterior.distance(pt) - 6) / 24
        reach = max(0.0, (Vec(px, py) - HUB).unit().dot(LIT)) ** 0.7
        if rng.random() < near**1.6 * reach:
            stip.circle((px, py), 1.2)

    # leaders: one gentle bow from each part to its ring marker
    lead, markers = P(), P()
    for (sx, sy), (ex, ey) in LEADERS:
        dx, dy, bow = ex - sx, ey - sy, math.copysign(0.12, ex - sx)
        tx = ex - math.copysign(MARK_R, dx)
        lead.M(sx, sy).Q((sx + tx) / 2 - dy * bow, (sy + ey) / 2 + dx * bow * 0.5, tx, ey)
        markers.circle((ex, ey), MARK_R)

    loop = Polygon(spline_points(FILAMENT, 16))
    with s.group(transform=place, stroke_linecap="round", stroke_linejoin="round"):
        s.fill(P().shape(ins), BG_ALT)
        s.stroke(dense, UI, 1.2)
        s.stroke(ruled, UI_ALT, 1.2)
        s.fill(stip, UI_ALT)
        # the glow: offset rings round the filament that stop higher up and dissolve into
        # shortening dashes one GLOW rung lower
        with s.buckets(GLOW, "stroke", stroke_width=1.3) as glow:
            for off, cut, tone in HALOS:
                ring = loop.buffer(off, quad_segs=24).exterior.intersection(box(-300, 0, 300, cut))
                for g in parts(ring.intersection(inner)):
                    if isinstance(g, LineString):
                        n = g.length
                        glow[tone].shape(substring(g, 40, n - 40))
                        for a, b in ((22, 34), (10, 17), (2, 5)):
                            glow[tone - 1].shape(substring(g, a, b))
                            glow[tone - 1].shape(substring(g, n - b, n - a))
        s.stroke(crests, UI_HI, 1.6)
        s.stroke(fine, UI_HI, 1.3)
        s.stroke(edge, UI_HI, 1.6)
        s.fill(shade, UI_HI)
        s.path(clamps, fill=BG, stroke=UI_HI, stroke_width=1.3)
        s.stroke(P().spline(FILAMENT), ACCENT, 2.6)
        s.stroke(lead, UI_ALT, 1.3)
        s.stroke(markers, UI_HI, 1.4)
        s.stroke(P().M(-56, 914).H(56), UI_ALT, 2)

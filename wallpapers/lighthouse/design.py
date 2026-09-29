"""Patent-style elevation of a lighthouse on its rock, the lamp's rays ruled out across the sea."""

import math

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_4,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Color,
    P,
    Path,
    Rect,
    Stop,
    clamp,
    design,
    ladder,
    smoothstep,
)
from walldye.geom import Affine, hatch, poisson_disk

# The scene is drawn in its 16:9 drafting coordinates and placed by one transform, so the tower
# foot at (CX, HORIZON) lands where the layout puts it; sky and sea run to the canvas edges.
CX = 470
PLINTH, PLINTH_HW = 842, 122
SHAFT_TOP, HW_BASE, HW_TOP = 470, 92, 60
DECK, DECK_HW = 450, 96  # underside of the gallery slab
RAIL = 40
GLAZE_TOP, LANT_HW = 316, 50
DOME_H = 46
LAMP = (CX, 356)
HORIZON = 880
BEAM = (math.radians(-7.4), math.radians(-1.4))
HALF = 8  # beam half-height at the lamp
REACH = 1410  # lamp to the beam's far end at 16:9; longer beams narrow to stay in the sky
GLITTER = 820  # length of the run of glints at 16:9
FOOT = 938  # waterline at the foot of the rock
# rock silhouette left to right; the plinth sits on the flat between x 348 and 592
ROCK = [
    (222, FOOT),
    (246, 918),
    (268, 910),
    (292, 890),
    (318, 880),
    (348, 864),
    (592, 864),
    (616, 872),
    (640, 884),
    (666, 888),
    (698, 906),
    (728, 916),
    (770, FOOT),
]
RIDGES = [
    ((268, 910), (300, FOOT)),
    ((318, 880), (372, FOOT)),
    ((616, 872), (602, FOOT)),
    ((666, 888), (650, FOOT)),
    ((698, 906), (706, FOOT)),
]
# (polygon, hatch angle in degrees, spacing); spacing tightens into the shade, the lit facet
# at the far left is left bare
FACETS = [
    ([(268, 910), (292, 890), (318, 880), (372, FOOT), (300, FOOT)], 58, 24),
    ([(318, 880), (348, 864), (592, 864), (616, 872), (602, FOOT), (372, FOOT)], 62, 13),
    ([(616, 872), (640, 884), (666, 888), (650, FOOT), (602, FOOT)], 52, 6),
    ([(666, 888), (698, 906), (706, FOOT), (650, FOOT)], 64, 4.5),
    ([(698, 906), (728, 916), (770, FOOT), (706, FOOT)], 46, 4),
]
# waterline ripples at the rock's foot: (x from, x to, depth below FOOT)
LAPPING = [
    (214, 330, 8),
    (352, 520, 8),
    (540, 640, 8),
    (660, 790, 8),
    (232, 290, 15),
    (700, 800, 15),
]
# the beam's reflection, brightest nearest the tower
GLINTS = ladder((BG, ACCENT_4, ACCENT), 14)[3:11][::-1]


def hw(y: float) -> float:
    """Half-width of the tapered shaft at height `y`."""
    return HW_TOP + (HW_BASE - HW_TOP) * (y - SHAFT_TOP) / (PLINTH - SHAFT_TOP)


def shade(u: float) -> float:
    """Darkness across a cylinder at u in [-1, 1], lit from the upper left."""
    nx, nz = u, math.sqrt(max(0.0, 1 - u * u))
    return 1 - max(0.0, -0.6 * nx + 0.8 * nz)


def hatch_us(lo_step: float = 0.05, hi_step: float = 0.2, start: float = -0.2) -> list[float]:
    """Hatch positions across [-1, 1], spacing tightening into the shade, none on the lit side."""
    out, u = [], start
    while u < 0.995:
        out.append(u)
        u += hi_step + (lo_step - hi_step) * shade(u) ** 0.7
    return out


def arched(cx: float, y0: float, w: float, h: float) -> Polygon:
    """Round-headed opening `w` wide and `h` tall with the crown of its arch at y0."""
    r = w / 2
    arc = [
        (cx + r * math.cos(math.pi * i / 16), y0 + r - r * math.sin(math.pi * i / 16))
        for i in range(17)
    ]
    return Polygon([*arc, (cx - r, y0 + h), (cx + r, y0 + h)])


def ramp_stops(
    color: Color, a0: float, x0: float, x1: float, end: float, n: int = 14
) -> list[Stop]:
    """Stops for a gradient running x0 to `end` whose opacity eases from a0 to 0 by x1
    (smoothstep, so it shows no banding)."""
    return [
        (clamp((x - x0) / (end - x0)), color, a0 * (1 - smoothstep(x0, x1, x)))
        for x in (x0 + (x1 - x0) * i / n for i in range(n + 1))
    ]


@design(aspects="any")
def draw(s: Canvas) -> None:
    # 16:9 keeps the tower foot at (470, 860); a phone is width-bound, so the figure grows there
    foot = s.pick(landscape=(CX / 1920, 860 / 1080), portrait=(0.33, 0.72))
    k = 1.0 if s.landscape else 1.15
    place = Affine.translate(foot.x, foot.y) @ Affine.scale(k) @ Affine.translate(-CX, -HORIZON)
    x0, y0 = place.inverse()((0, 0))
    x1, y1 = place.inverse()((s.w, s.h))

    r = s.rng(4)
    ruled, fine, outline, heavy = P(), P(), P(), P()
    lx, ly = LAMP
    glaze_x = CX + LANT_HW

    # beam: a triangle from the lamp that leaves the glazing ~21 units tall, then opens towards
    # the right edge; a screen narrower than 16:9 crops it rather than shortening it
    reach = max(REACH, x1 - 40 - lx)
    far = lx + reach
    narrow = min(1.0, (REACH / reach) ** 0.7)
    top, bottom = BEAM[0] * narrow, BEAM[1] * narrow

    def edge(t: float, x: float) -> tuple[float, float]:
        a = top + (bottom - top) * t
        return x, ly - HALF + 2 * HALF * t + (x - lx) * math.tan(a)

    fade = s.linear_gradient(
        ramp_stops(ACCENT, 0.3, lx, lx + 0.872 * reach, far), (lx, 0), (far, 0)
    )
    beam = P().poly(
        [(lx, ly), edge(0, glaze_x), edge(0, far), edge(1, far), edge(1, glaze_x)], closed=True
    )
    ray_end = glaze_x + 0.956 * (far - glaze_x)
    ray_fade = s.linear_gradient(
        ramp_stops(ACCENT, 1, glaze_x, ray_end, far), (glaze_x, 0), (far, 0)
    )
    rays = P()
    # inner rays start further out so the fan opens from its two edges instead of a solid block
    for i, lag in enumerate([0, 160, 60, 240, 110, 200, 70, 150, 0]):
        rays.M(edge(i / 8, glaze_x + lag)).L(edge(i / 8, far))

    # a sparse sky of pinpoint stars, kept clear of the tower and the beam
    stars = P()
    for x, y in poisson_disk(Rect(x0, y0, x1 - x0, HORIZON - 120 - y0), 150, s.rng(9)).tolist():
        a = math.atan2(y - ly, x - lx)
        if abs(x - CX) < 160 or (x > CX and top - 0.06 < a < bottom + 0.05) or r.random() < 0.5:
            continue
        stars.circle((x, y), 1.5)

    # glitter: the beam's reflection as a run of dashes on the open water right of the rock,
    # shrinking and fading outwards, fewer where a narrow screen leaves less water; the sea
    # leaves a gap round each dash
    g0 = ROCK[-1][0] + 50
    run = min(GLITTER, x1 - 60 - g0)
    n = max(3, math.ceil(len(GLINTS) * run / GLITTER))
    glints: list[tuple[int, float, float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        x = g0 + run * t**0.8 + r.uniform(-20, 20)
        yy = HORIZON + (9, 16, 24.4)[r.choice((0, 1, 1, 2)) if t > 0.1 else 0]
        glints.append((round(t * (len(GLINTS) - 1)), x, yy, 64 * (1 - t) ** 1.3 + 8))
    lit = unary_union([box(x - 36, yy - 4, x + ln + 36, yy + 4) for _, x, yy, ln in glints])

    # sea: patent-drawing water, short horizontals opening out towards the viewer, parted by the
    # rock and its lapping water
    rock = Polygon(ROCK)
    dry = unary_union([rock.buffer(12), box(ROCK[0][0] - 20, FOOT, ROCK[-1][0] + 30, FOOT + 22)])
    sea = P()
    y, gap = HORIZON + 9, 7.0
    while y < y1:
        x = x0 + r.uniform(-60, 0)
        while x < x1:
            ln = r.uniform(40, 200) * (1 + (y - HORIZON) / 180)
            if r.random() < 0.5:
                swell = LineString([(max(x, x0), y), (min(x + ln, x1), y)])
                sea.shape(swell.difference(dry).difference(lit))
            x += ln + r.uniform(30, 110)
        y += gap
        gap *= 1.2
    horizon = P().shape(LineString([(x0, HORIZON), (x1, HORIZON)]).difference(rock.buffer(4)))

    # rock: faceted planes stepping down to the waterline, lit from the upper left
    for pts, deg, step in FACETS:
        for seg in hatch(Polygon(pts).buffer(-3), step, deg=deg):
            ruled.poly(seg)
    # facet ridges run from the silhouette's corners down to the waterline
    for a, b in RIDGES:
        fine.M(a).L(b)
    for xa, xb, dy in LAPPING:
        fine.M(xa, FOOT + dy).H(xb)
    split = ROCK.index((CX + PLINTH_HW, 864))
    outline.poly(ROCK[: split + 1])
    heavy.poly(ROCK[split:])

    # plinth
    outline.M(CX - PLINTH_HW, 864).V(PLINTH).H(CX + PLINTH_HW)
    heavy.M(CX + PLINTH_HW, PLINTH).V(864)
    outline.M(CX - PLINTH_HW, 864).H(CX + PLINTH_HW)
    for u in hatch_us(0.035, 0.16):
        ruled.M(CX + u * PLINTH_HW, PLINTH + 4).V(860)

    # shaft: hatched along its taper, openings cut out
    openings = [arched(CX, 764, 34, 64), arched(CX - 8, 662, 18, 30), arched(CX + 6, 566, 16, 28)]
    holes = unary_union([o.buffer(5) for o in openings])
    for u in hatch_us():
        rule = LineString(
            [(CX + u * (HW_TOP - 2), SHAFT_TOP + 4), (CX + u * (HW_BASE - 2), PLINTH - 4)]
        )
        ruled.shape(rule.difference(holes))
    for o in openings:
        outline.shape(o.exterior)
        ox0, oy0, ox1, oy1 = o.bounds
        heavy.M(ox1, oy0 + (ox1 - ox0) / 2).V(oy1)  # shade line down the jamb, below the arch
    outline.M(CX - HW_TOP, SHAFT_TOP).L(CX - HW_BASE, PLINTH)
    heavy.M(CX + HW_TOP, SHAFT_TOP).L(CX + HW_BASE, PLINTH)
    for yc in (620, 716):
        outline.M(CX - hw(yc) - 4, yc).H(CX + hw(yc) + 4)

    # gallery: corbel flare, slab, railing
    outline.M(CX - HW_TOP, SHAFT_TOP).Q(CX - HW_TOP, DECK, CX - DECK_HW + 6, DECK)
    heavy.M(CX + HW_TOP, SHAFT_TOP).Q(CX + HW_TOP, DECK, CX + DECK_HW - 6, DECK)
    for u in hatch_us(0.06, 0.2):
        ruled.M(CX + u * (HW_TOP + 2), SHAFT_TOP - 3).V(DECK + 4)
    slab = DECK - 12
    outline.M(CX - DECK_HW, DECK).V(slab).H(CX + DECK_HW).M(CX - DECK_HW, DECK).H(CX + DECK_HW)
    heavy.M(CX + DECK_HW, slab).V(DECK)
    rail = slab - RAIL
    for i in range(-5, 6):
        outline.M(CX + i * 17.2, slab).V(rail)
    outline.M(CX - 90, rail).H(CX + 90).M(CX - 90, rail + 14).H(CX + 90)

    # lantern: glazed drum with diagonal astragals, domed roof, vent ball and rod
    base = rail - 2
    frame = box(CX - LANT_HW + 1, GLAZE_TOP + 1, CX + LANT_HW - 1, base)
    for i in range(-8, 9):
        for dx in (30, -30):
            bar = LineString([(CX + i * 17, GLAZE_TOP), (CX + i * 17 + dx, base)])
            fine.shape(bar.intersection(frame))
    outline.M(CX - LANT_HW, base).V(GLAZE_TOP).M(CX - LANT_HW, base).H(CX + LANT_HW)
    heavy.M(CX + LANT_HW, GLAZE_TOP).V(base)
    for yr in (GLAZE_TOP, GLAZE_TOP - 6):
        outline.M(CX - LANT_HW - 6, yr).H(CX + LANT_HW + 6)
    dr, dy = LANT_HW + 2, GLAZE_TOP - 6
    outline.M(CX + dr, dy).A(dr, DOME_H, 0, 0, 0, CX - dr, dy)
    for u in hatch_us(0.07, 0.22, 0.1):
        ruled.M(CX + u * (dr - 2), dy - 2).V(dy - DOME_H * math.sqrt(1 - u * u) + 3)
    vy = dy - DOME_H - 8
    outline.circle((CX, vy), 8).M(CX, vy - 8).V(vy - 52)

    # lens: stacked Fresnel prism rings about the lamp, the only solid accent
    lens: Path = P()
    for i in range(-4, 5):
        yk = ly + i * 7.5
        half = 32 * math.sqrt(max(0.0, 1 - (i / 5.2) ** 2))
        lens.M(lx - half, yk).Q(lx, yk + 3, lx + half, yk)

    with s.group(transform=place):
        s.fill(beam, fade)
        s.stroke(rays, ray_fade, 1.3)
        s.fill(stars, UI_ALT)
        s.stroke(sea, BG_ALT, 1.3)
        with s.buckets(GLINTS, "stroke", stroke_width=1.4, stroke_linecap="round") as b:
            for tone, x, yy, ln in glints:
                b[tone].M(x, yy).H(x + ln)
        s.stroke(horizon, UI, 1.2)
        s.stroke(fine, UI, 1.2)
        s.stroke(ruled, UI_ALT, 1.2)
        s.stroke(lens, ACCENT_1, 1.4)
        s.fill(P().circle(LAMP, 5), ACCENT)
        s.stroke(outline, UI_HI, 1.6, cap="round", join="round")
        s.stroke(heavy, UI_HI, 3, cap="round", join="round")

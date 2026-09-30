"""Circumpolar star trails over a row of spruces, drawn as line arcs around an off-canvas pole."""

import math

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    P,
    Vec,
    by_regime,
    design,
    polar,
    smoothstep,
)

SWEEP = 38  # degrees each star turns during the exposure
FOCUS_R, FOCUS_DEG = 1370, 46  # the middle lit trail's midpoint, seen from the pole
# Lit trails: radius offset from FOCUS_R, start angle from FOCUS_DEG (degrees), tone, width.
# Adjacent starts alternate so the heads never line up.
LIT = ((-140, -29, ACCENT_1, 1.8), (0, -19, ACCENT, 2.4), (150, -30, ACCENT_1, 1.8))
TIERS = ((BG_ALT, 1.0), (UI, 1.3), (UI_ALT, 1.8))  # faint, plain and bright trails
AREA = 1920 * 1080  # trail and bright-trail counts are per this much canvas
# the land sits one step darker than the sky: BG_DEEP on a dark theme, BG_ALT on a light one
LAND, SKYLINE = by_regime(BG_DEEP, BG_ALT), by_regime(BG_ALT, UI)


def tree(x: float, g: float, h: float, w: float, tiers: int) -> list[Polygon]:
    """A conifer rooted at (x, g), `h` tall and `w` half-wide at the base: a short trunk,
    `tiers` stacked narrowing tiers with drooping tips, and a thin spire."""
    parts = [
        Polygon(
            [(x - 1.2, g + 4), (x + 1.2, g + 4), (x + 1.2, g - h * 0.2), (x - 1.2, g - h * 0.2)]
        )
    ]
    for k in range(tiers):
        yb = g - h * (0.1 + 0.68 * k / tiers)
        yt = yb - h * (0.95 / tiers + 0.1)
        hw = w * (1 - 0.62 * k / tiers)
        parts.append(
            Polygon([(x - hw, yb + h * 0.03), (x, yt), (x + hw, yb + h * 0.03), (x, yb - h * 0.04)])
        )
    parts.append(Polygon([(x - 1.1, g - h * 0.82), (x, g - h), (x + 1.1, g - h * 0.82)]))
    return parts


def ridge(s: Canvas, base: float) -> Polygon:
    """The ground below a noisy skyline around `base`, with a forest along it: a low canopy
    where the forest is dense and taller spruces rising from it. Holes are filled."""
    n = s.noise(3)
    xs = np.arange(-12, s.w + 13, 4.0)
    ground = base - 110 * n.fbm(xs / 900, 0.3, 3) - 16 * n.fbm(xs / 180, 5.1, 2)
    shapes = [Polygon([(-12, s.h + 20), *zip(xs, ground, strict=True), (s.w + 12, s.h + 20)])]
    rt = s.rng(5)
    # back rank: a low, continuous canopy wherever the forest is dense
    for x in np.arange(-12, s.w + 12, 7.0):
        if n(x / 260, 9.7) > -0.15:
            h = rt.uniform(10, 20)
            shapes += tree(x, float(np.interp(x, xs, ground)) + 3, h, h * 0.8, 1)
    # front rank: individual spruces that rise clear of the canopy
    x = -12.0
    while x < s.w + 12:
        dense = n(x / 260, 9.7) > -0.15
        h = rt.uniform(34, 80) if dense else rt.uniform(18, 40)
        shapes += tree(
            x,
            float(np.interp(x, xs, ground)) + 3,
            h,
            h * rt.uniform(0.2, 0.34),
            rt.choice([3, 3, 4]),
        )
        x += rt.uniform(14, 40) if dense else rt.uniform(40, 110)
    land = unary_union(shapes)
    if not isinstance(land, Polygon):
        raise TypeError("the forest came apart from the ground")
    return Polygon(land.exterior)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the middle lit trail's midpoint; the pole sits off-canvas up and to its left
    focus = s.pick(landscape=(0.3915, 0.6347), portrait=(0.42, 0.52))
    pole = focus - polar((0, 0), FOCUS_R, deg=FOCUS_DEG)
    per = s.w * s.h / AREA
    far = max(abs(Vec(x, y) - pole) for x in (0, s.w) for y in (0, s.h))
    # midpoint angles span the margin box around the canvas, and at least the quadrant below
    # and right of the pole
    box = [math.atan2(y - pole.y, x - pole.x) for x in (-200, s.w + 200) for y in (-200, s.h)]
    lo, hi = min(0, *box) - 0.2, max(math.pi / 2, *box) + 0.2
    lit_r = [FOCUS_R + dr for dr, *_ in LIT]

    rnd = s.rng(11)
    trails = [P() for _ in TIERS]
    count = bright = 0
    while count < round(360 * per):
        r = rnd.uniform(280, far + 70)
        a0 = rnd.uniform(lo, hi) - math.radians(SWEEP) / 2
        mid = polar(pole, r, rad=a0 + math.radians(SWEEP) / 2)
        if not (-200 < mid.x < s.w + 200 and -200 < mid.y < s.h):
            continue
        # thin the right and upper-right so windows there sit on quiet texture
        quiet = smoothstep(focus.x - 50, s.w - 20, mid.x) * (
            0.6 + 0.4 * smoothstep(0.65 * s.h, 0, mid.y)
        )
        if rnd.random() < 0.8 * quiet or any(abs(r - lr) < 14 for lr in lit_r):
            continue
        count += 1
        m = rnd.random() ** 4 * (1 - 0.7 * quiet)
        if m > 0.6 and bright < round(15 * per) and mid.x < focus.x + 750:
            bright += 1
            tier = 2
        else:
            tier = 1 if m > 0.2 else 0
        trails[tier].arc(pole, r, rad=(a0, a0 + math.radians(SWEEP)))
    for d, (tone, w) in zip(trails, TIERS, strict=True):
        s.stroke(d, tone, w, cap="round")
    for (_, da, tone, w), r in zip(LIT, lit_r, strict=True):
        a0 = FOCUS_DEG + da
        s.stroke(P().arc(pole, r, deg=(a0, a0 + SWEEP)), tone, w, cap="round")

    land = ridge(s, s.h - 108)
    s.path(P().shape(land), fill=LAND, stroke=SKYLINE, stroke_width=1, stroke_linejoin="round")

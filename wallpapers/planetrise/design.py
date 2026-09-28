"""The limb of a vast planet hatched with latitude circles, rimmed by a glowing atmosphere, with a small crescent moon above."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_5,
    BG,
    BG_ALT,
    BG_DEEP,
    MASK_WHITE,
    Canvas,
    P,
    Path,
    Vec,
    design,
    mix,
)
from walldye.field import runs

R_PER_W = 1.875  # planet radius per unit of canvas width, so the limb spans every screen
TILT = math.radians(52)  # north pole tilted up from facing the viewer, at most
POLE_BELOW = 233  # the pole projects at least this far below the bottom edge
LAT_STEP = 1.5  # degrees between latitude circles
MAX_LAT = 72  # the tight polar circles near the bottom edge would read as a ripple target
MOON_R = 19
GLOW = 70


def latitudes(s: Canvas, c: Vec, r: float, tilt: float) -> Path:
    """The visible front arcs of the planet's latitude circles, cut to the canvas."""
    pole = np.array([0, -math.sin(tilt), math.cos(tilt)])
    u = np.array([1.0, 0, 0])
    v = np.cross(pole, u)
    t = np.linspace(0, 2 * math.pi, round(1440 * r / 3600))
    ring = np.outer(u, np.cos(t)) + np.outer(v, np.sin(t))
    hatch = P()
    for lat in np.radians(np.arange(-88, MAX_LAT + 1, LAT_STEP)):
        p = (pole * r * math.sin(lat))[:, None] + r * math.cos(lat) * ring
        x, y = c.x + p[0], c.y + p[1]
        vis = (p[2] > 0) & (y < s.h + 20) & (x > -20) & (x < s.w + 20)
        for a, b in runs(vis):
            if b - a > 2:
                hatch.poly(np.column_stack([x[a:b], y[a:b]]))
    return hatch


@design(aspects="any")
def draw(s: Canvas) -> None:
    r = R_PER_W * s.w
    top = s.pick(landscape=(0.5833, 0.5093), portrait=(0.5833, 0.7))
    c = top + (0, r)
    disc = P().circle(c, r)
    # tall screens show more of the planet; tilting less keeps the pole's circles out of frame
    tilt = min(TILT, math.asin(1 - (s.h - top.y + POLE_BELOW) / r))

    # lit from the right like the moon, with a faint floor so the left limb still glows
    with s.mask() as side:
        lit = side.linear_gradient([(0, MASK_WHITE, 0.35), (0.75, MASK_WHITE)], (0, 0), (s.w, 0))
        side.fill(P().rect(0, 0, s.w, s.h), lit)
    glow = s.radial_gradient([(r / (r + GLOW), ACCENT_5), (1, BG, 0)], c, r + GLOW)
    s.path(P().circle(c, r + GLOW), fill=glow, mask=side.ref)
    # stacked translucent rings: the atmosphere melts outward over ~10 px instead of ending on a hard edge
    for i in range(8):
        s.stroke(disc, ACCENT_5, 2.5 * (i + 1), opacity=0.2)
    s.fill(disc, BG_DEEP)

    with s.mask() as fade:
        down = fade.linear_gradient([(0, MASK_WHITE), (1, MASK_WHITE, 0.25)], top, (top.x, s.h))
        fade.fill(P().rect(0, 0, s.w, s.h), down)
    with s.group(mask=fade.ref):
        s.stroke(latitudes(s, c, r, tilt), BG_ALT, 1.2)

    sun = s.linear_gradient([(0, ACCENT_2), (0.7, ACCENT)], (0, 0), (s.w, 0))
    s.stroke(disc, sun, 2)

    m = s.pick(landscape=(0.2396, 0.2222), portrait=(0.3, 0.2))
    s.fill(P().circle(m, MOON_R), mix(BG, BG_ALT, 0.5))
    lit_side = (
        P()
        .M(m.x, m.y - MOON_R)
        .A(MOON_R, MOON_R, 0, 0, 1, m.x, m.y + MOON_R)
        .A(MOON_R * 0.45, MOON_R, 0, 0, 0, m.x, m.y - MOON_R)
        .Z()
    )
    s.fill(lit_side, ACCENT)

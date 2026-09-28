"""A bowl seen from above, its cracks mended with lacquer seams of varying width and one rim chip filled solid."""

import math

import numpy as np
from numpy.typing import NDArray
from shapely import get_coordinates
from shapely.geometry import LineString, Point
from shapely.ops import substring

from walldye import (
    ACCENT,
    ACCENT_1,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_HI,
    Canvas,
    P,
    Vec,
    clamp,
    design,
    mix,
    polar,
)
from walldye.field import Noise, gauss
from walldye.geom import ribbon

type Pts = NDArray[np.float64]

R, LIP, FOOT = 360, 16, 150  # bowl radius, rim band width, foot ring radius
# rim chip where the tee crack starts: angle (deg), half its span (deg), greatest depth
CHIP, CHIP_HALF, CHIP_DEPTH = 116, math.degrees(40 / R), 16


def crack(n: Noise, row: float, p0: Vec, p1: Vec, amp: float, step: float = 3.0) -> Pts:
    """Points every ~`step` from p0 to p1, pushed sideways by up to ~`amp` of slow noise
    (`n` read along x = `row`) that fades out at both ends."""
    d = p1 - p0
    length = abs(d)
    t = np.linspace(0, 1, max(8, int(length / step)))
    u = t * length
    off = amp * (n(row, u / 170) + 0.35 * n(row + 9, u / 60)) * np.sin(np.pi * t) ** 0.5
    return p0 + np.outer(t, d) + np.outer(off, d.perp() / length)


def tee_into(line: Pts, other: Pts) -> Pts:
    """`line` cut off at its first crossing with `other`, ending exactly on it."""
    ls = LineString(line)
    hits = get_coordinates(ls.intersection(LineString(other)))
    k = min(ls.project(Point(p)) for p in hits)
    return np.asarray(substring(ls, 0, k).coords, dtype=np.float64)


def lacquer(
    n: Noise, pts: Pts, row: float, *, swell: Pts | None = None, taper: bool = False
) -> Pts:
    """Seam width at each point: about 4 with slow noise (`n` read along x = `row`), bulging over
    ~18 units around the vertex nearest `swell`, and narrowing toward the end when `taper`."""
    along = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    w = 4 + 0.9 * n(row, along / 190)
    if swell is not None:
        j = int(np.argmin(np.hypot(*(pts - swell).T)))
        w += 1.4 * gauss(along - along[j], 18)
    if taper:
        w *= clamp(1.15 * (1 - along / along[-1]) ** 0.7, 0.3, 1)
    return w


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of centre on a landscape screen; centred in the upper part of a portrait one
    c = s.pick(landscape=(0.65625, 0.5), portrait=(0.5, 0.41))

    def rim(deg: float, inset: float = 0) -> Vec:
        return polar(c, R - inset, deg=deg)

    s.fill(P().circle(c + (14, 22), R + 6), BG_DEEP)  # cast shadow, down and to the right
    s.fill(P().circle(c, R), mix(BG_ALT, UI, 0.2))
    s.stroke(P().circle(c, R - LIP / 2), mix(BG_ALT, UI, 0.35), LIP)
    # the well: lit near the wall, falling to background tone toward the centre, shaded away
    # from the upper left
    rw = R - LIP
    well = s.radial_gradient([(0, BG), (0.4 * R / rw, BG), (1, BG_ALT)], c, rw)
    s.fill(P().circle(c, rw), well)
    shade = s.radial_gradient(
        [(0, BG_DEEP, 0), (0.7, BG_DEEP, 0.1), (1, BG_DEEP, 0.6)], c + (50, 60), R + 30
    )
    s.fill(P().circle(c, rw), shade)
    foot = P().circle(c, FOOT)
    s.fill(foot, BG_DEEP, opacity=0.3)
    s.stroke(foot, UI, 1.2, opacity=0.5)
    s.stroke(P().circle(c, R), UI, 1.2)

    # rim catchlight across the upper left, fading out at both ends
    glint = s.linear_gradient(
        [(0, UI_HI, 0), (0.5, UI_HI, 0.9), (1, UI_HI, 0)], rim(175, 2.5), rim(275, 2.5)
    )
    s.stroke(P().arc(c, R - 2.5, deg=(175, 275)), glint, 2.4)

    # one long meander rim to rim, one crack teeing into it, one short crack in from the rim
    n = s.noise(4)
    main = crack(n, 1.3, rim(214), rim(8), amp=34)
    tee = tee_into(crack(n, 5.7, rim(CHIP), c + (90, -200), amp=24), main)
    short = crack(n, 8.1, rim(296), rim(296 + math.degrees(0.14), 135), amp=12)
    seams = [
        (main, lacquer(n, main, 2.2, swell=tee[-1])),
        (tee, lacquer(n, tee, 6.4, swell=tee[-1])),
        (short, lacquer(n, short, 9.9, taper=True)),
    ]
    groove, seam = P(), P()
    for pts, w in seams:
        groove.poly(ribbon(pts, w + 2), closed=True)
        seam.poly(ribbon(pts, w), closed=True)
    s.fill(groove, BG_DEEP)
    s.fill(seam, ACCENT)

    # a sliver flaked off the rim where the tee crack starts, filled solid; deeper on the
    # crack's side
    edge = [
        rim(
            CHIP + CHIP_HALF * (1 - 2 * k),
            CHIP_DEPTH * math.sin(math.pi * k) ** 0.9 * (1.05 - 0.1 * k),
        )
        for k in np.linspace(0, 1, 24)
    ]
    s.fill(P().spline(edge).A(R, R, 0, 0, 1, edge[0]).Z(), ACCENT_1)

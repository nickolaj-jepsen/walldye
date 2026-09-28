"""The last seconds of an Outer Wilds loop: a to-scale orbit chart crossed by the supernova front in error-diffused dither cells."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_4,
    ACCENT_6,
    BG,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    Point,
    Rect,
    Vec,
    design,
    knob,
    polar,
)
from walldye.field import cells, falloff, gauss, noise_grid
from walldye.pixel import dither, grid_runs


class Loop(Params):
    front: float = knob(
        default=10000,
        lo=5600,
        hi=22000,
        unit="m",
        doc="radius the supernova front has reached, in game metres",
    )


# The front just past the Hourglass Twins, with Timber Hearth still ahead of it.
VARIANTS = {"early": Loop(front=5700)}

# Geometry is the game's own (PacificEngine OW_CommonResources Planet.cs): semi-major axes,
# moon orbits and body radii in metres, drawn at K px per metre on a 16:9 screen.
K = 0.07
BODY = 0.6  # body radii shrink by this much more, so bodies stay dots
TWINS, TH, BH, GD, DB = 5000, 8593, 11691, 16458, 20000
WHITE_HOLE = 23000
# Angles off the chart axis are arbitrary (no reliable end-of-loop ephemeris), kept on screen.
ANG = {TWINS: -34, TH: 21, BH: -13, GD: 12, DB: -9}
CELL = 3
CORE_R, HALO_R = 5, 26  # collapsed sun: bright core and Bayer halo, px
WAKE = 200  # depth of the sparse wake behind the front, px


def grid_box(s: Canvas, c: Point, r: float) -> Rect:
    """The square of whole cells around `c` out to `r`, clipped to the canvas."""
    x0 = max(0, math.floor((c[0] - r) / CELL) * CELL)
    y0 = max(0, math.floor((c[1] - r) / CELL) * CELL)
    x1 = min(s.w, math.ceil((c[0] + r) / CELL) * CELL)
    y1 = min(s.h, math.ceil((c[1] + r) / CELL) * CELL)
    return Rect(x0, y0, x1 - x0, y1 - y0)


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Loop]) -> None:
    front = s.params.front
    # The chart runs right on landscape and down on portrait, and shrinks on screens shorter
    # than 1920 along it; on longer ones the sun moves in to show more of the far side (on a
    # phone, far enough that an early front clears the top edge), and once that would put it
    # past Giant's Deep's orbit, the whole system is shown.
    long = max(s.w, s.h)
    z = min(1.0, long / 1920)
    k, kr = K * z, K * z * BODY
    back = 200 * z + (0.55 if s.landscape else 0.75) * max(0, long - 1920)
    if back > GD * k:
        back = DB * k + 150
    axis = 0 if s.landscape else 90
    c = s.pick(landscape=(back / s.w, 590 / 1080), portrait=(490 / 1080, back / s.h), snap=CELL)

    def at(m: float, deg: float, o: Point = c) -> Vec:
        return polar(o, m * k, deg=axis + deg)

    orbits = P()
    for a in ANG:
        orbits.circle(c, a * k)
    s.stroke(orbits, UI, 1)

    # Bodies the front has passed are burnt out: knocked out to the ground with a faint rim.
    dead, live = P(), P()

    def body(pos: Point, r: float, orbit: int) -> None:
        (dead if orbit < front else live).circle(pos, r * kr)

    # Hourglass Twins: Ash and Ember, 250 m either side of the barycentre, along the orbit.
    bary = at(TWINS, ANG[TWINS])
    t = (bary - c).unit().perp() * (250 * k)
    body(bary - t, 170, TWINS)
    body(bary + t, 170, TWINS)

    # Timber Hearth with the Attlerock, and Brittle Hollow with Hollow's Lantern, each on a
    # dashed moon orbit.
    th, bh = at(TH, ANG[TH]), at(BH, ANG[BH])
    s.stroke(P().circle(th, 900 * k).circle(bh, 1000 * k), UI_ALT, 1, dash=(3, 4))
    body(th, 250, TH)
    body(at(900, 150, th), 100, TH)
    body(bh, 300, BH)
    lantern = at(1000, -115, bh)

    # Dark Bramble: a small core, crooked vines out to a broken ice shell at ~650 m, as on
    # the ship's Planetary Chart.
    db = at(DB, ANG[DB])
    rng = s.np_rng(11)
    vines, shell = P(), P()
    for i in range(9):
        a = 2 * math.pi * i / 9 + rng.uniform(-0.25, 0.25) + math.radians(axis)
        r1 = 650 * kr * rng.uniform(0.72, 1.0)
        bend = a + rng.uniform(-0.3, 0.3)
        vines.poly(
            [polar(db, 200 * kr, rad=a), polar(db, r1 * 0.55, rad=bend), polar(db, r1 - 2, rad=a)]
        )
        w = rng.uniform(0.12, 0.24)
        shell.arc_band(db, r1 - 2.5, r1 + 1.5, rad=(a - w, a + w))
    s.stroke(vines, UI_ALT, 1, join="round")
    s.fill(shell, UI_ALT)
    body(db, 200, DB)

    # Giant's Deep: the ocean (500 m) inside its storm atmosphere (900 m); by far the largest.
    gd = at(GD, ANG[GD])
    s.stroke(P().circle(gd, 900 * kr), UI_ALT, 1)
    body(gd, 500, GD)

    s.fill(live, UI_HI)
    s.fill(P().circle(bh, 300 * kr * 0.4), BG)  # the hollow around Brittle Hollow's singularity
    if BH < front:
        dead.circle(lantern, 130 * kr)
    else:
        s.fill(P().circle(lantern, 130 * kr), MUTED)
    s.path(dead, fill=BG, stroke=UI_HI, stroke_width=1.2)

    # Where Brittle Hollow's singularity comes out: stationary, so it has no orbit ring.
    s.stroke(P().circle(at(WHITE_HOLE, 4), 4), UI_HI, 1)

    # Collapsed sun: a tiny bright core with a short Bayer falloff.
    box = grid_box(s, c, HALO_R + CELL)
    xs, ys = cells(box, CELL)
    r = np.hypot(xs - c.x, ys - c.y)
    tone = np.where(r < CORE_R, 1.0, 0.7 * falloff(r - CORE_R, HALO_R - CORE_R, 2.4))
    halo = dither(tone, 4, method="bayer", matrix=8)
    grid_runs(s, halo, [None, UI, UI_HI, MUTED], CELL, (box.x, box.y))

    # Supernova shell: one crisp front, a gap, then a sparse wake thinning toward the sun.
    rf = front * k
    box = grid_box(s, c, rf + 30)
    xs, ys = cells(box, CELL)
    rows, cols = xs.shape
    r = np.hypot(xs - c.x, ys - c.y)
    ang = np.arctan2(ys - c.y, xs - c.x) - math.radians(axis)
    wob = noise_grid(cols, rows, 40, s.np_rng(7), octaves=3)
    d = r - (rf + 5 * np.sin(3 * ang + 1.2) + 4 * wob)
    crest = np.where(d > 0, gauss(d, 3.5), gauss(d, 5))
    wake = np.where(d < -10, 0.085 * gauss(d + 40, 55), 0)
    v = np.maximum(crest, wake) * (1 + 0.1 * noise_grid(cols, rows, 18, s.np_rng(3), octaves=3))
    v[(r < rf - WAKE) | (r > rf + 30)] = 0
    shock = dither(v, 5, method="atkinson", serpentine=True)
    grid_runs(s, shock, [None, ACCENT_6, ACCENT_4, ACCENT_2, ACCENT], CELL, (box.x, box.y))

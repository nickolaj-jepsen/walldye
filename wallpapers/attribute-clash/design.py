"""A night road on a ZX Spectrum screen in ordered dither, drawn in 8x8 attribute cells."""

import numpy as np

from walldye import ACCENT, BG, BG_ALT, BG_DEEP, UI_HI, Canvas, P, Vec, by_regime, design, mix
from walldye.pixel import Pixels

SW, SH, ATTR = 256, 192, 8  # Spectrum screen in pixels; attribute cell side
BORDER = 8  # screen border, in pixels
PAPER, INK, LIT = 0, 1, 2  # screen palette indices
VX, HZ = 127, 91  # vanishing point column, horizon row
SLOPE = 0.42  # road half-width per row below the horizon
CAR = """
.......############.......
......##.#.#.#.#.#.#......
.....##.#.#.#.#.#.#.#.....
....##.#.#.#.#.#.#.#.#....
.########################.
#........................#
#.LL.......####.......LL.#
#........................#
##########################
.###..................###.
"""
CAR_X, CAR_Y = 114, 150
STREAKS = (2, 3, 5, 8, 12, 17, 23)  # rows of wet-road reflection below the bumper
# BG_DEEP recedes on a dark ground but vanishes on paper, so half a BG_ALT step frames it there.
BORDER_TONE = by_regime(BG_DEEP, mix(BG, BG_ALT, 0.5))


@design(aspects="any")
def draw(s: Canvas) -> None:
    # A portrait screen is too narrow for 4-unit pixels plus the border.
    px = 4 if s.landscape else 3
    size = Vec(SW, SH) * px
    c = s.pick(landscape=(0.7, 0.493), portrait=(0.5, 0.4), snap=px)
    # keep the border clear of the right edge on narrow landscapes (16:10)
    c = Vec(min(c.x, s.w - size.x / 2 - 2 * BORDER * px), c.y)
    o = c - size / 2

    ys, xs = np.mgrid[0:SH, 0:SW]
    cols = np.arange(SW)
    sky = 0.22 * np.clip((ys - HZ + 40) / 40, 0, 1) ** 1.8
    # the sparsest Bayer level reaches the bottom edge
    ground = 0.035 + 0.2 * np.clip(1 - (ys - HZ) / (SH - HZ), 0, 1) ** 1.6
    tone = np.where(ys < HZ, sky, ground)
    ridge = np.round(HZ - 7 - 5 * np.sin(cols / 23 + 1) - 3 * np.sin(cols / 9 + 2)).astype(int)
    tone[(ys > ridge) & (ys < HZ)] = 0.5
    # the road plus a clear verge for the posts
    tone[(ys > HZ) & (np.abs(xs - VX) < (ys - HZ) * SLOPE * 1.22 + 2)] = 0

    scr = Pixels(SW, SH, [None, UI_HI, ACCENT])
    scr.dither(tone, [PAPER, INK])
    scr.grid[HZ, :] = INK
    scr.grid[ridge, cols] = INK
    r = s.rng(9)
    for _ in range(14):  # stars
        scr.grid[r.randrange(4, HZ - 34), r.randrange(4, SW - 4)] = INK

    for side in (-1, 1):
        # aimed past the bottom edge so the curb keeps its slope to the last row
        end = round(VX + side * SLOPE * (SH + 20 - HZ))
        scr.line(VX, HZ, end, SH + 20, INK)
        for k in range(1, 9):  # verge posts, evenly spaced in depth
            z = 1.15 * k
            y = round(HZ + 100 / z)
            x = round(VX + side * (SLOPE * 100 / z * 1.11 + 2))
            scr.grid[y - max(1, round(10 / z)) + 1 : y + 1, x] = INK
    dash = np.zeros(SH, bool)
    for z in np.arange(0.9, 12, 0.7).tolist():  # center dashes
        dash[round(HZ + 100 / (z + 0.25)) : round(HZ + 100 / z)] = True
    dash[CAR_Y - 4 : CAR_Y + 10] = False  # a gap, so the dash doesn't read as an aerial
    scr.grid[dash, VX] = INK

    scr.stamp(CAR, CAR_X, CAR_Y, {".": PAPER, "#": INK, "L": INK})
    rows = CAR.strip().split("\n")
    lamps = [(j, i) for j, row in enumerate(rows) for i, ch in enumerate(row) if ch == "L"]
    lit = np.zeros((SH, SW), bool)
    for j, i in lamps:
        lit[CAR_Y + j, CAR_X + i] = True
    # Tail-light reflections streak down the wet road, one under each lamp.
    for i in sorted({i for _, i in lamps})[::2]:
        for k in STREAKS:
            lit[CAR_Y + len(rows) + k, CAR_X + i : CAR_X + i + 2] = True
    scr.grid[lit] = INK

    # One ink per attribute cell: every ink pixel in a cell that holds a light turns LIT.
    cells = lit.reshape(SH // ATTR, ATTR, SW // ATTR, ATTR).any(axis=(1, 3))
    clash = cells.repeat(ATTR, 0).repeat(ATTR, 1)
    scr.grid[clash & (scr.grid == INK)] = LIT

    b = BORDER * px
    frame = P().rect(o.x - b, o.y - b, size.x + 2 * b, size.y + 2 * b)
    s.fill(frame.rect(o.x, o.y, size.x, size.y), BORDER_TONE, rule="evenodd")
    rules = P()
    for i in range(1, SW // ATTR):
        rules.M(o.x + i * ATTR * px, o.y).V(o.y + size.y)
    for j in range(1, SH // ATTR):
        rules.M(o.x, o.y + j * ATTR * px).H(o.x + size.x)
    s.stroke(rules, BG_ALT, 1)
    scr.draw(s, px, o)

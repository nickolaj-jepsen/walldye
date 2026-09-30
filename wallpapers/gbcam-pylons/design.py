"""Pylons at dusk as a Game Boy Camera photo in four-shade Bayer dither on a thermal strip."""

from itertools import pairwise

import numpy as np
from scipy.ndimage import zoom

from walldye import (
    ACCENT,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Point,
    Vec,
    by_regime,
    design,
)
from walldye.field import noise_grid
from walldye.geom import bezier_points
from walldye.pixel import Pixels, glyphs

PW, PH, CELL = 128, 112, 5  # the camera's frame in cells, and the cell size
# The camera's four shades, darkest first, then the lamp. On paper the shades run the other
# way, so the light print is a positive with the pylons in the strongest ink.
PALETTE = (
    by_regime(BG_DEEP, UI_HI),
    by_regime(BG_ALT, UI),
    by_regime(UI, BG_ALT),
    by_regime(UI_ALT, BG),
    ACCENT,
)
INK, LAMP = 0, 4
HORIZON = 80
VANISH = 96  # photo column the field's furrows converge on
FURROWS = (-10, 150)  # photo columns where the furrows leave the bottom edge
# Pylons in photo cells: base column, base row, height; the nearest one carries the lamp.
PYLONS = ((26, 100, 88), (80, 89, 42), (110, 84, 21))
MARGIN, CAPTION, TAIL, TOOTH = 26, 26, 104, 16  # paper around, above and below the photo

type Seg = tuple[Vec, Vec]


def pylon(x: float, base: float, h: float) -> tuple[list[Seg], list[Vec]]:
    """Lattice tower as photo-cell segments, plus its two wire anchors: the right insulator's
    end and the apex, where the lamp sits."""

    def half(u: float) -> float:  # leg half-width at height fraction u
        return 0.17 - 0.12 * u / 0.6 if u < 0.6 else 0.05 - 0.025 * (u - 0.6) / 0.4

    def p(dx: float, u: float) -> Vec:
        return Vec(x + dx * h, base - u * h)

    apex = p(0, 1.02)
    segs = [
        (p(-half(0), 0), p(-half(0.6), 0.6)),
        (p(-half(0.6), 0.6), p(-half(1), 0.94)),
        (p(half(0), 0), p(half(0.6), 0.6)),
        (p(half(0.6), 0.6), p(half(1), 0.94)),
        (p(-half(1), 0.94), apex),
        (p(half(1), 0.94), apex),
    ]
    n = 4 if h > 60 else 3 if h > 30 else 2
    # X panels only in the legs, shrinking upward
    us = [0.6 * (1 - (1 - k / n) ** 1.3) for k in range(n + 1)]
    for u0, u1 in pairwise(us):
        segs += [
            (p(-half(u0), u0), p(half(u1), u1)),
            (p(half(u0), u0), p(-half(u1), u1)),
            (p(-half(u1), u1), p(half(u1), u1)),
        ]
    u, span = 0.74, 0.3
    drop = 2 / h  # insulators hang one or two cells below the arm tip
    for sgn in (-1, 1):
        segs += [
            (p(sgn * half(u), u), p(sgn * span, u)),
            (p(sgn * span, u), p(sgn * half(u + 0.1), u + 0.1)),
            (p(sgn * span, u), p(sgn * span, u - drop)),
        ]
    # Only the right conductor and the earth wire off the peak are strung, so no wire crosses
    # a tower.
    return segs, [p(span, u - drop), apex]


def line(px: Pixels, a: Point, b: Point) -> None:
    """Ink the cells of the line from a to b, its ends rounded to whole cells."""
    px.line(round(a[0]), round(a[1]), round(b[0]), round(b[1]), INK)


@design(aspects="any")
def draw(s: Canvas) -> None:
    size = Vec(PW * CELL, PH * CELL)
    # Right of center on a landscape screen, the left kept for windows; in the upper part of a
    # portrait one. Half the photo is whole cells, so the snapped center gives a snapped origin.
    o = s.pick(landscape=(0.7474, 0.363), portrait=(0.5, 0.33), snap=CELL) - size / 2

    rows, cols = np.mgrid[0:PH, 0:PW]
    # Shade units 0..3: the dusk sky stays within shades 1..2 and only the horizon band reaches 3.
    t = np.clip(rows / HORIZON, 0, 1)
    # wind-stretched cloud bands
    streak = zoom(noise_grid(PW // 6 + 1, PH, 6, s.np_rng(2), octaves=2), (1, 6), order=1)
    sky = (
        1.2
        + 0.95 * t**2.2
        + 0.5 * np.clip(streak[:, :PW], 0, None) * (1 - t)
        + 0.6 * np.clip((rows - HORIZON + 10) / 10, 0, 1)
    )
    sky -= 0.35 * ((cols - PW / 2) / PW) ** 2 * 4 * (1 - t)  # lens falloff in the upper corners
    img = np.where(rows < HORIZON, np.maximum(sky, 1.0), 1.0)  # the field is one flat shade

    px = Pixels(PW, PH, PALETTE)
    px.dither(img / 3, range(4), method="bayer", matrix=4)
    ridge = noise_grid(PW, 1, 7, s.np_rng(9), octaves=2)[0]
    trees = HORIZON - 1 - 3 * np.clip(ridge + 0.3, 0, None)  # tree-line top per column
    px.grid[(rows >= trees[cols]) & (rows < HORIZON + 1)] = INK

    # Furrows converge on the horizon; they start a few rows down so the tree line stays clean.
    for bx in FURROWS:
        line(px, (VANISH + (bx - VANISH) * 0.12, HORIZON + 4), (bx, PH + 4))

    anchors: list[list[Vec]] = []  # wire anchors per pylon, near to far
    for x, base, h in PYLONS:
        segs, ends = pylon(x, base, h)
        for a, b in segs:
            line(px, a, b)
        anchors.append(ends)
    # Two sagging wires per span; the near pylon ends the line.
    for near, far in pairwise(anchors):
        for a, b in zip(near, far, strict=True):
            sag = 0.09 * abs(b.x - a.x)
            pts = bezier_points([a, (a + b) / 2 + (0, 2 * sag), b], 79)
            for u, v in pairwise(pts):
                line(px, u, v)

    ax, ay = round(anchors[0][1].x), round(anchors[0][1].y)
    px.grid[ay - 1 : ay + 1, ax - 1 : ax + 1] = LAMP

    # Paper strip: outline only, so it doesn't lift a tall slab off the background; big torn
    # teeth at the foot.
    x0, x1, bot = o.x - MARGIN, o.x + size.x + MARGIN, o.y + size.y + TAIL
    teeth = [
        (x1 - k * TOOTH, bot - (TOOTH // 2 if k % 2 else 0))
        for k in range(int((x1 - x0) // TOOTH) + 1)
    ]
    s.stroke(P().poly([(x1, -4), *teeth, (x0, bot), (x0, -4)]), UI_ALT, 2, join="miter")

    px.draw(s, CELL, o, skip=None)

    cap = o + (0, size.y + CAPTION)
    glyphs(s, "No.07", lambda c, r, ch: ACCENT if ch == "7" else UI_HI, at=cap, font="5x8", px=3)
    glyphs(s, "98.09.27", UI, at=cap + (size.x, 0), font="5x8", px=3, anchor="end")

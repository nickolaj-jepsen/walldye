"""Pixel-art bonsai in a shallow tray; autumn has turned one pad's tip and a leaf drifts down."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    design,
)
from walldye.field import gauss
from walldye.geom import Polyline
from walldye.pixel import Pixels

type Field = NDArray[np.float64]
type Mask = NDArray[np.bool_]
type Spine = tuple[tuple[float, float, float], ...]

CELL = 7
# Tones from recessed to lit; a turned leaf takes its tone TURN places up the palette.
DEEP, SHADE, BODY, SIDE, LIT = 1, 2, 3, 4, 5
TURN = 5
PALETTE = (None, BG_DEEP, BG_ALT, UI, UI_ALT, UI_HI, None, ACCENT_5, ACCENT_3, ACCENT_1, ACCENT)

# Positions are in cells from the centre of the pot's rim.
# Trunk spine (x, y, radius), pot to apex; the branches fork off it.
TRUNK: Spine = (
    (-2, 2, 8.5),
    (-2, -2, 5.4),
    (-3, -5, 4.3),
    (-6, -9, 3.8),
    (-3, -16, 3.3),
    (6, -23, 2.8),
    (8, -31, 2.4),
    (1, -39, 2.0),
    (-4, -46, 1.7),
    (-1, -52, 1.4),
)
BRANCHES: tuple[Spine, ...] = (
    ((-4, -15, 1.8), (-12, -18, 1.6), (-22, -21, 1.3), (-30, -23, 1.1)),
    ((6, -26, 1.8), (17, -30, 1.5), (26, -34, 1.1)),
    ((1, -38, 1.6), (-8, -41, 1.3), (-14, -43, 1.1)),
)
# Foliage pads (cx, cy, rx, ry); the second one turns at its tip.
PADS = ((-29, -25, 17, 5.5), (29, -37, 15, 5), (-14, -44, 10, 4), (-1, -55, 12, 5.5))
TREE = (-66, 0, -54, 54)  # the rows and columns the trunk, branches and pads stay within
POT_W, POT_H = 46, 7
TABLE, MARGIN = 70, 11  # the table runs 70 cells past the pot but stops 11 short of the edge
LEAF = (".aa", "abc")
LEAF_KEY = {"a": LIT + TURN, "b": SIDE + TURN, "c": BODY + TURN}


def spine(pts: Spine, origin: tuple[int, int]) -> list[tuple[float, float, float]]:
    """Samples (x, y, radius) every quarter cell along a spine, moved to `origin`."""
    a = np.array(pts, dtype=np.float64)
    line = Polyline(a[:, :2] + origin)
    seg = np.diff(line.pts, axis=0)
    knots = np.concatenate([[0.0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
    d = np.append(np.arange(0.0, line.length, 0.25), line.length)
    xy, r = line.at(d), np.interp(d, knots, a[:, 2])
    return list(zip(xy[:, 0].tolist(), xy[:, 1].tolist(), r.tolist()))


def limb(
    px: Field, py: Field, samples: list[tuple[float, float, float]], across_x: bool
) -> tuple[Mask, Field]:
    """Cells inside a limb, and a smooth -1..1 lighting coordinate across it (x for the trunk,
    y for a branch). Each cell averages its offsets from the nearby samples, so the shading has
    no seams where they overlap."""
    inside = np.zeros(px.shape, dtype=bool)
    num, den = np.zeros(px.shape), np.full(px.shape, 1e-9)
    for x, y, r in samples:
        dx, dy = px - x, py - y
        d = np.hypot(dx, dy)
        inside |= d < r
        w = gauss(d, r / math.sqrt(3))
        num += w * (dx if across_x else dy) / r
        den += w
    return inside, num / den


@design(aspects="any")
def draw(s: Canvas) -> None:
    pix = Pixels(s.w // CELL, s.h // CELL, PALETTE)
    rim = s.pick(landscape=(0.62, 0.622), portrait=(0.5, 0.64), snap=CELL)
    ox, oy = round(rim.x / CELL), round(rim.y / CELL)

    # The tree is worked in a window of the grid that ends at the rim, where the trunk enters
    # the pot.
    top, bottom, left, right = TREE
    tree = pix.grid[oy + top : oy + bottom, ox + left : ox + right]
    j, i = np.mgrid[oy + top : oy + bottom, ox + left : ox + right]
    px, py = i + 0.5, j + 0.5

    # Branches lit from above, then the trunk lit from the left.
    for pts, across_x in [(b, False) for b in BRANCHES] + [(TRUNK, True)]:
        m, side = limb(px, py, spine(pts, (ox, oy)), across_x)
        tree[m] = np.where(side < -0.35, SIDE, np.where(side < 0.35, BODY, SHADE))[m]

    # Pads: a flat-bottomed cluster of bumps; lit scalloped top rim, mid body, shaded underside.
    rng = s.np_rng(21)
    pads: list[Mask] = []
    for cx, cy, rx, ry in PADS:
        cx, cy = cx + ox, cy + oy
        pad = np.zeros(tree.shape, dtype=bool)
        n = int(rx / 3.2)
        for k in range(n + 1):
            u = -1 + 2 * k / n
            bx = cx + u * rx * 0.82 + rng.uniform(-1, 1)
            by = cy - ry * 0.25 * math.sqrt(max(0, 1 - u * u)) + rng.uniform(-0.6, 0.6)
            br = ry * (0.95 - 0.35 * abs(u)) + rng.uniform(0, 0.8)
            pad |= (px - bx) ** 2 + ((py - by) * 1.15) ** 2 < br * br
        pad &= py < cy + ry * 0.6
        above, above2, below = np.roll(pad, 1, 0), np.roll(pad, 2, 0), np.roll(pad, -1, 0)
        tone = np.where(~above, LIT, np.where(~above2, SIDE, np.where(~below, SHADE, BODY)))
        tree[pad] = tone[pad]
        pads.append(pad)

    # Autumn has reached the second pad's tip: the same shading, moved onto the accent ramp past
    # a clean stepped edge.
    cx, cy = PADS[1][0] + ox, PADS[1][1] + oy
    tree[pads[1] & ((i - cx) + (j - cy) // 2 >= 4)] += TURN

    # Pot: shallow tray, lip lit on the left half, recessed body, two feet over a shadow strip
    # on the table line.
    g = pix.grid
    x0, x1, y0 = ox - POT_W // 2, ox + POT_W // 2, oy
    g[y0 : y0 + 2, x0 - 1 : x1 + 1] = BODY
    g[y0, x0 - 1 : ox] = SIDE
    for k in range(2, POT_H):
        g[y0 + k, x0 + k // 3 : x1 - k // 3] = SHADE
    g[y0 + 2 : y0 + POT_H - 1, x0 + 1] = BODY
    foot = y0 + POT_H
    g[foot, x0 + 3 : x1 - 3] = DEEP
    for fx in (x0 + 5, x1 - 9):
        g[foot, fx : fx + 4] = BODY
    g[foot + 1, max(x0 - TABLE, MARGIN) : min(x1 + TABLE, pix.cols - MARGIN)] = SHADE

    # One leaf resting on the table, one drifting down below the turned tip.
    g[foot, x1 + 12 : x1 + 14] = SIDE + TURN
    pix.stamp(LEAF, cx + 16, cy + 10, LEAF_KEY)

    pix.draw(s, CELL)

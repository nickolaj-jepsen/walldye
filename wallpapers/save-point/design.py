"""A top-down pixel-tile dungeon room; a crystal on a pedestal at its centre dithers its light onto the stone floor."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_HI,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    Rng,
    by_regime,
    design,
    mix,
)
from walldye.field import falloff
from walldye.pixel import Pixels, dither

PX = 4  # canvas units per pixel
T = 16  # tile size in pixels
TILE = T * PX
WT = 2  # wall-top rows above the lit brick face, at least
MARGIN = 88  # least canvas space around the room outline
GLOW_R = 51  # pixels

type Tile = NDArray[np.int64]

# Pixel colour indices.
(
    FLOOR,
    SHADOW,
    SEAM,
    DETAIL,
    MORTAR,
    BRICK,
    LIT,
    TOP,
    RIM,
    DOOR,
    GLOW_LO,
    GLOW_HI,
    C_EDGE,
    C_BODY,
    C_FACET,
    C_HI,
    PED,
    PED_TOP,
    PED_LIT,
) = range(19)
COLORS = [
    BG,
    BG_DEEP,
    mix(BG, BG_ALT, 0.6),
    BG_ALT,
    BG_DEEP,
    BG_ALT,
    UI,
    BG_DEEP,
    UI,
    BG_DEEP,
    ACCENT_5,
    ACCENT_3,
    ACCENT_3,
    ACCENT,
    ACCENT_1,
    by_regime(ACCENT_HI, ACCENT_6),  # on paper a glint is less ink, not more
    UI,
    UI_ALT,
    ACCENT_5,
]
KEY = {"e": C_EDGE, "b": C_BODY, "f": C_FACET, "h": C_HI, "p": PED, "q": PED_TOP, "l": PED_LIT}

PEDESTAL = """
...qqqqqqqqqqqqqqqq...
..qqqqqqqqqqqqqqqqqq..
..qqqqqqllllllqqqqqq..
..pppppppppppppppppp..
..pppppppppppppppppp..
..pppppppppppppppppp..
.qqqqqqqqqqqqqqqqqqqq.
.pppppppppppppppppppp.
.pppppppppppppppppppp.
"""


def crystal() -> list[str]:
    """14x20 gem: lit left half, facet-shaded right half and a highlight streak."""
    hw = [1, 2, 3, 4, 5, 6, 7, 7, 7, 7, 7, 6, 6, 5, 5, 4, 3, 3, 2, 1]
    rows = []
    for y, w in enumerate(hw):
        row = ["."] * 14
        for x in range(7 - w, 7 + w):
            edge = x in (7 - w, 6 + w) or y in (0, len(hw) - 1)
            row[x] = "e" if edge else "f" if x >= 7 else "b"
        if 2 <= y <= 8:
            row[5 if y < 6 else 4] = "h"
        rows.append("".join(row))
    return rows


def floor_tile(kind: str, r: Rng) -> Tile:
    """One stone floor tile of the given kind, its detail drawn from `r`."""
    t = np.full((T, T), FLOOR)
    if r.random() < 0.4:  # sparse corner ticks; a full lattice reads as graph paper
        for i, j in ((0, 0), (1, 0), (0, 1), (T - 1, 0), (0, T - 1)):
            t[j, i] = SEAM
    if kind == "crack":
        x, y = r.randint(3, 6), r.randint(4, 9)
        for _ in range(r.randint(5, 8)):
            t[y, x] = DETAIL
            x += 1
            if r.random() < 0.35:
                y = max(2, min(T - 3, y + r.choice((-1, 1))))
    elif kind == "pebbles":
        for _ in range(r.randint(2, 4)):
            x, y = r.randint(2, T - 4), r.randint(2, T - 4)
            t[y, x] = DETAIL
            if r.random() < 0.4:
                t[y, x + 1] = DETAIL
    elif kind == "worn":
        cx, cy = r.randint(5, 10), r.randint(5, 10)
        j, i = np.mgrid[0:T, 0:T]
        t[((i - cx) ** 2 + (j - cy) ** 2 < 14) & ((i + j) % 2 == 0)] = SEAM
    return t


def wall_face() -> Tile:
    """A brick tile in running bond, each course lit along its top pixel row."""
    t = np.full((T, T), BRICK)
    for j in range(T):
        if j % 4 == 0:
            t[j, :] = MORTAR
            continue
        for i in range(T):
            if (i + (j // 4 % 2) * 4) % 8 == 0:
                t[j, i] = MORTAR
            elif j % 4 == 1:
                t[j, i] = LIT
    return t


def door_tile(left: bool) -> Tile:
    """Half of a recessed north doorway: dark opening with a lit jamb on its outer side."""
    t = np.full((T, T), DOOR)
    t[0, :] = RIM
    t[:, 0 if left else T - 1] = RIM
    return t


@design(aspects="any")
def draw(s: Canvas) -> None:
    # The room outline (brick face top to south rim) is the largest whole-tile room that leaves
    # MARGIN on every side; an even floor width centres the doorway over the crystal.
    floor_cols = int((s.w - 2 * MARGIN) // TILE) // 2 * 2
    floor_rows = int((s.h - 2 * MARGIN) // TILE) - 1  # the brick face takes one row
    room_w, room_h = floor_cols * TILE, (floor_rows + 1) * TILE
    x0 = round((s.w - room_w) / 2 / PX) * PX
    y0 = round((s.h - room_h) / 2 / PX) * PX
    # Wall tiles run past the canvas edge on every side.
    left = max(2, math.ceil(x0 / TILE))
    right = max(2, math.ceil((s.w - x0 - room_w) / TILE))
    top = max(WT, math.ceil(y0 / TILE))
    bottom = max(2, math.ceil((s.h - y0 - room_h) / TILE))
    tc, tr = left + floor_cols + right, top + 1 + floor_rows + bottom
    origin = (x0 - left * TILE, y0 - top * TILE)

    wall = np.ones((tr, tc), bool)
    wall[top + 1 : top + 1 + floor_rows, left : left + floor_cols] = False
    door = (left + floor_cols // 2 - 1, left + floor_cols // 2)
    face = wall_face()
    kinds = ["plain"] * 12 + ["crack", "crack", "pebbles", "pebbles", "worn"]
    px = Pixels(tc * T, tr * T, COLORS)
    g = px.grid
    r = s.rng(16)
    for ty in range(tr):
        for tx in range(tc):
            if ty == top and tx in door:
                tile = door_tile(tx == door[0])
            elif ty == top and left <= tx < left + floor_cols:
                tile = face
            elif wall[ty, tx]:
                tile = np.full((T, T), TOP)
            else:
                tile = floor_tile(r.choice(kinds), r)
            g[ty * T : (ty + 1) * T, tx * T : (tx + 1) * T] = tile

    # Lit rim on wall tops wherever they meet a walkable or face pixel.
    tops = g == TOP
    g[tops & ndimage.binary_dilation(~tops)] = RIM

    # Contact shadow: one dark pixel row where the floor meets the wall above it.
    fl = ~np.repeat(np.repeat(wall, T, 0), T, 1)
    g[fl & ~np.roll(fl, 1, 0) & (g == FLOOR)] = SHADOW

    cx = round((s.center.x - origin[0]) / PX)
    cy = round((s.center.y - origin[1]) / PX)
    gy = cy - 16  # gem top; its point rests in the pedestal's top face
    ped = PEDESTAL.strip("\n").split("\n")
    px.stamp(ped, cx - 11, gy + 18, KEY)
    px.stamp(crystal(), cx - 7, gy, KEY)
    g[gy + 18 + len(ped), cx - 10 : cx + 10] = SHADOW

    # Two dithered glow layers on bare floor, kept two pixels clear of the gem and pedestal.
    yy, xx = np.mgrid[0 : tr * T, 0 : tc * T]
    d = np.hypot(xx - cx, yy - (gy + 12))
    lo = dither(falloff(d, GLOW_R, 2.6) * 0.6, 2, method="bluenoise", rng=s.np_rng(3))
    hi = dither(falloff(d, 0.4 * GLOW_R, 1.4) * 0.7, 2, method="bluenoise", rng=s.np_rng(7))
    halo = ndimage.binary_dilation(g >= C_EDGE, np.ones((5, 5), bool))
    free = ((g == FLOOR) | (g == SEAM)) & ~halo
    g[(lo == 1) & free] = GLOW_LO
    g[(hi == 1) & free] = GLOW_HI

    px.draw(s, PX, origin)

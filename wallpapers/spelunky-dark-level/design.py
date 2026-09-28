"""A Spelunky dark level in pixel art: one wall torch, and only the blocks inside its Bayer-dithered circle of light."""

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from scipy.spatial import cKDTree

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_7,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    FG_ALT,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    NpRng,
    Vec,
    by_regime,
    design,
    mix,
    smoothstep,
)
from walldye.field import falloff
from walldye.pixel import dither, grid_runs, sprite

type Grid = NDArray[np.int64]

CELL = 6
TILE = 16  # cells per 96-unit tile: the in-game camera shows about 20 tiles across
OY = 6  # the view starts 6 cells into the 12-tile-tall level, which overhangs it top and bottom
COLS, ROWS = 320, 180  # the view in cells: the 16:9 frame, which holds the whole circle of light

# Spelunky Classic scrRoomGen templates, obstacle chunks and "2" (50% block) resolved: left =
# main room case 4, right = side room case 3 (high wall with ladder); a row of the rooms above
# and below.
LEFT = [
    "1110000000",
    "1100001110",
    "0000000100",
    "0000111000",
    "0000000000",
    "0001101100",
    "0011111100",
    "1111111111",
]
RIGHT = [
    "0000000011",
    "0000000L04",
    "0001110P11",
    "0000000L11",
    "0000000L11",
    "0001100011",
    "0001110011",
    "1111111111",
]
MAP = (
    ["11000000111100000011", "11111111111111111111"]
    + [a + b for a, b in zip(LEFT, RIGHT, strict=True)]
    + ["11111111111111111111", "11110011111111001111"]
)
SOLID = np.array([[ch in "14" for ch in row] for row in MAP])
LADDER = np.array([[ch in "LP" for ch in row] for row in MAP])
TCOL, TROW = 14, 6  # torch tile: on the back wall, resting on the rubble mound

# Spelunky 2 wall torch (s2_wall_torch): rock head bound in rope, stake through a riveted plate.
TORCH = """
..kkk.kkk..
.kRrrkRrrk.
kRrrkRrrRrk
krRrkrrkrrk
kyyyyyyyyyk
kYyyyyyyyYk
kkYYyyyYYkk
.kyyyyyyyk.
.kYyyyyyYk.
..kYYyYYk..
..kyyyyyk..
...kYYYk...
...kwWWk...
.kpppppppk.
.kpbpbpbpk.
.kpppppppk.
.kpppppppk.
..kkwWWkk..
...kwWWk...
....kWk....
....kk.....
"""
FLAME = """
.....o....
.....oo...
..o..ao...
..oo.aao..
...oaaao..
..oaacaao.
.oaaccaao.
.oacccaaoo
.oaccccao.
.oacccaao.
..oacaao..
..ooaaoo..
"""
# Torch sprite origin in view units, centred on its tile; the stake tip rests on the mound.
TX = TCOL * TILE * CELL + (TILE - 11) * CELL // 2
TY = ((TROW + 1) * TILE - OY - len(TORCH.split())) * CELL
FLAME_AT = (TX + 5.5 * CELL, TY - 5 * CELL)  # the light source, in view units
R_IN, R_OUT = 350, 490  # full light inside R_IN, none beyond R_OUT

# Terrain tones, index 0 (air in full light) not drawn: mortar, stone underside, stone, lit lip,
# the outline in dim and in full light, and the back wall. Then, per light level: air (level 0
# is the unlit dark), back wall and ladder. Tones 1-4 brighten with the index in both regimes, so
# capping one by the light level dims it. On light screens the unlit dark is DARK and lit air is
# the page, and outlines take ink; on dark screens air and dark are both the background.
MORTAR, SHADE, STONE, LIP, EDGE_DIM, EDGE, WALL = 1, 2, 3, 4, 5, 6, 7
AIR, ROCK, RUNG = 8, 11, 14  # plus the light level: air 0-3, back wall 1-3, ladder 1-4
DARK = MUTED
TERRAIN = (
    None,
    by_regime(BG_ALT, UI_HI),
    by_regime(UI, UI_ALT),
    by_regime(UI_ALT, UI),
    by_regime(UI_HI, BG_ALT),
    by_regime(BG_DEEP, MUTED),
    by_regime(BG_DEEP, FG_ALT),
    BG_ALT,
    *(by_regime(BG, mix(DARK, BG, k / 4)) for k in range(4)),
    *(by_regime(BG_ALT, mix(DARK, BG_ALT, k / 4)) for k in range(1, 4)),
    *(
        by_regime(dark, light)
        for dark, light in zip(
            (BG_ALT, UI, UI_ALT, UI_HI),
            (mix(DARK, UI_HI, 1 / 3), mix(DARK, UI_HI, 2 / 3), UI_HI, UI_ALT),
            strict=True,
        )
    ),
)
TORCH_KEY = {
    "k": by_regime(BLACK, FG_ALT),
    "r": UI_ALT,
    "R": UI_HI,
    "y": MUTED,
    "Y": UI_HI,
    "w": UI_ALT,
    "W": UI,
    "p": UI,
    "b": UI_HI,
}
FLAME_KEY = {"o": ACCENT_3, "a": ACCENT_1, "c": ACCENT}


def stones(
    rng: NpRng, pitch: int, shape: tuple[int, int], gap: float, periodic: bool = False
) -> Grid:
    """Rounded stones on a weighted, jittered Voronoi of cell size `pitch`, as a (rows, cols)
    label image with 0 for mortar. `gap` is the mortar width in cells; `periodic` tiles a square
    `shape` seamlessly (random seeds instead of a jittered lattice)."""
    rows, cols = shape
    if periodic:
        n = rows
        base = rng.uniform(0, n, (int((n / pitch) ** 2), 2))
        pts = np.concatenate([base + (dx * n, dy * n) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
        w = np.tile(rng.uniform(0.7, 1.4, len(base)), 9)
        ids = np.tile(np.arange(len(base)), 9) + 1
    else:
        gy, gx = np.mgrid[-1 : rows // pitch + 2, -1 : cols // pitch + 2]
        jx, jy = rng.uniform(0.1, 0.9, gx.shape), rng.uniform(0.1, 0.9, gy.shape)
        pts = np.stack([(gx + jx) * pitch, (gy + jy) * pitch], -1).reshape(-1, 2)
        w = rng.uniform(0.7, 1.45, len(pts))  # a few big stones among smaller ones
        ids = np.arange(len(pts)) + 1
    ys, xs = np.mgrid[0:rows, 0:cols]
    q = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], -1)
    d, k = cKDTree(pts).query(q, k=6)
    d = d / w[k]
    o = np.argsort(d, 1)
    d1 = np.take_along_axis(d, o[:, :1], 1)[:, 0]
    d2 = np.take_along_axis(d, o[:, 1:2], 1)[:, 0]
    lab = ids[np.take_along_axis(k, o[:, :1], 1)[:, 0]].reshape(shape)
    inside = ((d2 - d1) * pitch / 4 > gap).reshape(shape)
    disk = np.array([[0, 1, 1, 0], [1, 1, 1, 1], [1, 1, 1, 1], [0, 1, 1, 0]], bool)
    if periodic:
        inside = ndimage.binary_opening(np.tile(inside, (3, 3)), disk)[rows:-rows, cols:-cols]
    else:
        inside = ndimage.binary_opening(inside, disk)
    return np.where(inside, lab, 0)


def on_canvas(s: Canvas, grid: Grid, cell: int, origin: Vec, fill: int = 0) -> tuple[Grid, Vec]:
    """The cells that cover the canvas when `grid` is drawn from `origin` in cells of `cell`
    units: `grid` cropped to the canvas and padded with `fill` where it falls short, with that
    block's origin. `origin` must be a whole number of cells."""
    c0, r0 = int(-origin.x // cell), int(-origin.y // cell)
    c1, r1 = -int((origin.x - s.w) // cell), -int((origin.y - s.h) // cell)
    rows, cols = grid.shape
    top, left = max(0, -r0), max(0, -c0)
    pad = ((top, max(0, r1 - rows)), (left, max(0, c1 - cols)))
    g = np.pad(grid, pad, constant_values=fill)
    return g[r0 + top : r1 + top, c0 + left : c1 + left], origin + (c0 * cell, r0 * cell)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # The flame right of centre and a little high on a landscape screen (the left stays dark
    # for windows), centred in the upper half on a portrait one; the view follows it.
    view = s.pick(landscape=(0.725, 4 / 9), portrait=(0.5, 0.4), snap=CELL) - FLAME_AT

    ys, xs = np.mgrid[0:ROWS, 0:COLS]
    tj, ti = (ys + OY) // TILE, xs // TILE
    solid = SOLID[tj, ti]

    # Round the convex corners of every exposed block so the silhouette steps by whole tiles only.
    cy, cx = (ys + OY) % TILE, xs % TILE
    mp = np.pad(SOLID, 1, constant_values=True)
    up, dn = ~mp[tj, ti + 1], ~mp[tj + 2, ti + 1]
    lf, rt = ~mp[tj + 1, ti], ~mp[tj + 1, ti + 2]
    rc = 3.5
    for vy, vx, oy, ox in (
        (up, lf, rc, rc),
        (up, rt, rc, TILE - rc),
        (dn, lf, TILE - rc, rc),
        (dn, rt, TILE - rc, TILE - rc),
    ):
        dy, dx = cy + 0.5 - oy, cx + 0.5 - ox
        outside = (dy * (1 if oy > TILE / 2 else -1) > 0) & (dx * (1 if ox > TILE / 2 else -1) > 0)
        solid &= ~(vy & vx & (np.hypot(dy, dx) > rc) & outside)

    pad = np.pad(solid, 1, constant_values=False)
    n_up = ~pad[:-2, 1:-1]
    n_dn = ~pad[2:, 1:-1]
    edge = solid & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])

    # Terrain: a few large rounded stones per tile set in dark mortar.
    lab = stones(s.np_rng(3), 8, (ROWS, COLS), 0.9)
    st = solid & (lab > 0)
    below = np.pad(lab, ((0, 1), (0, 0)))[1:]
    above = np.pad(lab, ((1, 0), (0, 0)))[:-1]
    tone = np.zeros(solid.shape, np.int64)
    tone[solid] = MORTAR
    tone[st] = STONE
    tone[st & (below != lab)] = SHADE  # the underside of each stone
    tone[st & (above != lab)] = LIP  # the upper lip of each stone, facing the torch
    # Smooth dirt rim on exposed tops, shadowed underside on exposed bottoms.
    rim = np.pad(n_up, ((1, 0), (0, 0)))[:-1] | np.pad(n_up, ((2, 0), (0, 0)))[:-2]
    tone[solid & ~n_up & rim] = LIP
    under = np.pad(n_dn, ((0, 1), (0, 0)))[1:] | np.pad(n_dn, ((0, 2), (0, 0)))[2:]
    tone[solid & under] = MORTAR

    # Ladder: two rails and a rung every quarter tile (classic sLadder).
    rails = np.isin(cx, (3, 4, 11, 12)) | ((cy % 4 == 1) & (cx > 3) & (cx < 12))
    ladder = LADDER[tj, ti] & rails
    tone[ladder] = STONE
    tone[ladder & np.isin(cx, (3, 11))] = LIP

    # Back wall: low-contrast lumpy rocks, one two-tile pattern repeated (sCaveBG).
    wl = stones(s.np_rng(5), 8, (2 * TILE, 2 * TILE), 1.8, periodic=True)
    wall = (wl[(ys + OY) % (2 * TILE), xs % (2 * TILE)] > 0) & ~solid & ~ladder

    fx, fy = FLAME_AT
    d = np.hypot((xs + 0.5) * CELL - fx, (ys + 0.5) * CELL - fy)
    lit = dither(smoothstep(R_OUT, R_IN, d), 5, method="bayer", matrix=8)

    g = np.minimum(tone, lit)
    g[wall & (lit > 0)] = WALL
    g[edge & (lit == 2)] = EDGE_DIM
    g[edge & (lit > 2)] = EDGE
    g[ladder & (g > 0)] += RUNG
    dim_wall, dim_air = (g == WALL) & (lit < 4), (g == 0) & (lit < 4)
    g[dim_wall] = ROCK + lit[dim_wall]
    g[dim_air] = AIR + lit[dim_air]
    part, at = on_canvas(s, g, CELL, view, fill=AIR)  # the level's dark runs past the view
    grid_runs(s, part, TERRAIN, CELL, at)

    # Torch glow: ACCENT_7 grains dithered on open air at half-cell size, densest at the flame.
    hc = CELL // 2
    hy, hx = np.mgrid[0 : ROWS * 2, 0 : COLS * 2]
    glow = falloff(np.hypot((hx + 0.5) * hc - fx, (hy + 0.5) * hc - fy), 150, 1.4) * 0.7
    hg = dither(glow, 2, method="bluenoise", rng=s.np_rng(7))
    hg[np.repeat(np.repeat(solid, 2, 0), 2, 1)] = 0
    part, at = on_canvas(s, hg, hc, view)
    grid_runs(s, part, (None, ACCENT_7), hc, at)

    sprite(s, TORCH, TORCH_KEY, CELL, view + (TX, TY))
    sprite(s, FLAME, FLAME_KEY, CELL, view + (TX, TY - 11 * CELL))

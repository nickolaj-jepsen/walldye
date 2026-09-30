"""An apartment tower at night in pixel art, with a few furnished rooms seen through windows."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    P,
    Rect,
    design,
    mix,
)
from walldye.field import noise_grid
from walldye.geom import poisson_disk
from walldye.pixel import dither, grid_runs, sprite

PX = 4
COLS, WW, WH = 6, 96, 80  # window columns; window opening in units (24x20 cells)
BAY, STORY, SIDE = 130, 114, 26  # window pitch across and down; wall beside the outer windows
TW = 2 * SIDE + BAY * (COLS - 1) + WW  # tower width
ROOF_GAP = 44  # roof edge to the top of the first window row
FOOT = 72  # last window's bottom to the canvas edge: the tower runs on below it
HOT_COL = 3
LIT, GHOSTS = 7, 2  # dim rooms and curtained dark ones in seven stories (a taller tower: sparser)

SILL = mix(BG_ALT, UI_ALT, 0.55)
BAND = mix(BG_ALT, UI_ALT, 0.35)
GRIME = mix(BG_ALT, UI, 0.3)
LAMP = mix(BG_ALT, UI, 0.7)
SHADE = mix(LAMP, BG, 0.5)
GHOST = mix(BG, BG_ALT, 0.5)


def pad(art: str) -> list[str]:
    """`art` as exactly 20 rows of 24 characters, padded with transparent '.' cells."""
    rows = [row.ljust(24, ".") for row in art.strip("\n").split("\n")]
    return (rows + ["." * 24] * 20)[:20]


BLIND = """
########################
++++++++++++++++++++++++
++++++++++++++++++++++++
########################
++++++++++++++++++++++++
++++++++++++++++++++++++
########################
++++++++++++++++++++++++
########################
...................#
...................#
...................#
..................###
"""
PLANT = """
.
.
.
.
.
.
.
.................#
..............#.##.#
...............###.##
.............##.#.#
..............#####
...............###
................#
..............#####
..............#####
...............###
...............###
"""
CAT = """
.
.
.
.
.
.
.........#...#
.........##.##
.........#####
.........#####
..........###
.........#####
........#######
........#######
.......#########
.......#########..#
.......#########..#
........#######..#
.........#######
"""
LAMP_STAND = """
.
.
.
..####
.######
########
...oo
...##
....#
....#
....#
....#
....#
....#
....#
....#
....#
....#
...###
"""
PENDANT = """
...........#
...........#
...........#
...........#
...........#
.........#####
........#######
.......#########
..........ooo
"""
SHELF = """
.
.
.
.
................########
................#.#..#.#
................#.#.##.#
................########
................##.#.#..
................##.#.#.#
................########
................#..###.#
................#.####.#
................########
................#......#
................#......#
"""
SOFA = """
.
.
.
.
.
.
.
.
.
.
.
.
.......###
......#####
......#####
.......###
..####################
.######################
.######################
.######################
"""
MOTIFS = (BLIND, PLANT, CAT, LAMP_STAND, PENDANT, SHELF, SOFA)
# a drawn curtain, barely there in an unlit room
CURTAIN = """
#######.
#######.
######.#
######.#
######.#
#####.##
#####.##
#####.##
####.##
####.##
####.##
###.##
###.##
####
####
#####
#####.
######.
######.#
#######.
"""
# '#' the coder, 'f' chair, desk and monitor, 's' the screen, 'l' lines of code
CODER = """
........................
........................
........................
...........ffffffffff...
...........fssssssssf...
...........fsllllsssf...
...........fssssssssf...
.......##..fslllllssf...
......####.fssssssssf...
......####.ffffffffff...
.......##.......ff......
....########....ff......
...##########.ffffff....
...##########fffffffff..
..f########f.........f..
..ffffffffff.........f..
..ffffffffff.........f..
..ffffffffff.........f..
...f......f..........f..
...f......f..........f..
"""


type Cell = tuple[int, int]  # (column, story) of a window


def apart(p: Cell, q: Cell) -> int:
    """Steps from one window to another along the facade grid (Manhattan distance)."""
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def fit(art: str, flip: bool) -> list[str]:
    """Center a motif's columns in the 24x20 opening with at least one '.' cell each side,
    mirrored left to right when `flip`."""
    rows = pad(art)
    used = [i for i in range(24) if any(r[i] != "." for r in rows)]
    lo, hi = max(used[0], 1), min(used[-1], 22)
    start = (24 - (hi - lo + 1)) // 2
    rows = [("." * start + r[lo : hi + 1]).ljust(24, ".") for r in rows]
    return [r[::-1] for r in rows] if flip else rows


@design(aspects="any")
def draw(s: Canvas) -> None:
    r = s.rng(5)
    # Whole stories stack up from the bottom edge, so the tower always runs off it the same way;
    # a landscape screen holds seven, a portrait one about twice as many under a taller sky.
    aim = s.pick(landscape=(0.5, 0.185), portrait=(0.5, 0.29))
    stories = round((s.h - FOOT - WH - ROOF_GAP - aim.y) / STORY) + 1
    wy0 = s.h - FOOT - WH - STORY * (stories - 1)  # top of the first window row
    roof = wy0 - ROOF_GAP
    tx0 = round((s.w - TW) / 2 / PX) * PX
    tx1 = tx0 + TW
    event = s.pick(landscape=(0, 0.58), portrait=(0, 0.55))
    hot = (HOT_COL, round((event.y - WH / 2 - wy0) / STORY))
    cells = [(c, rw) for c in range(COLS) for rw in range(stories)]

    def at(p: Cell) -> tuple[int, int]:
        """Top-left corner of window `p`'s opening."""
        return tx0 + SIDE + BAY * p[0], wy0 + STORY * p[1]

    s.fill(P().rect(tx0, roof, TW, s.h - roof), BG_ALT)

    # weathering: Riemersma grain that only switches on above ~0.2, a little denser lower down
    gy0 = roof // PX * PX  # on the cell grid; the coping hides any sliver above the roof
    cols, rows = TW // PX, (s.h - gy0) // PX
    stain = noise_grid(cols, rows, 30, s.np_rng(4), octaves=3)
    depth = np.arange(rows)[:, None] / rows
    grime = dither(0.26 + 0.35 * stain + 0.06 * depth, 2, method="riemersma")
    for x, y in (at(p) for p in cells):
        # clear the cells a window and its sill cover completely; they would never show
        for x0, y0, x1, y1 in ((x, y, x + WW, y + WH + 4), (x - 4, y + WH, x + WW + 4, y + WH + 4)):
            i0, i1 = -(-(x0 - tx0) // PX), (x1 - tx0) // PX
            j0, j1 = -(-(y0 - gy0) // PX), (y1 - gy0) // PX
            grime[j0:j1, i0:i1] = 0
    grid_runs(s, grime, [BG_ALT, GRIME], PX, (tx0, gy0))
    bands = P()
    for k in range(stories):
        bands.rect(tx0, wy0 - 20 + STORY * k, TW, 2)
    s.fill(bands, BAND)

    # roofline: a lift housing, its cap, a mast with a crossbar, and the coping
    s.fill(P().rect(tx1 - 250, roof - 64, 150, 64), BG_ALT)
    roofline = P().rect(tx1 - 256, roof - 70, 162, 6)
    roofline.rect(tx0 + 150, roof - 150, 4, 150).rect(tx0 + 140, roof - 110, 24, 4)
    s.fill(roofline.rect(tx0 - 8, roof - 8, TW + 16, 8), UI)

    stars = P()
    for x, y in poisson_disk(Rect(0, 0, s.w, s.h), 170, r):
        if (x < tx0 - 30 or x > tx1 + 30 or y < roof - 180) and y < s.h - 180:
            stars.rect(round(x / 2) * 2, round(y / 2) * 2, 2, 2)
    s.fill(stars, UI_ALT)

    # the event's neighbors stay dark
    far = [p for p in cells if abs(p[0] - hot[0]) > 1 or abs(p[1] - hot[1]) > 1]
    grow = math.sqrt(stories / 7)
    n_lit, n_ghosts = round(LIT * grow), round(GHOSTS * grow)
    lit: list[Cell] = []
    ghosts: list[Cell] = []
    for p in r.sample(far, len(far)):
        if len(lit) < n_lit and all(apart(p, q) > 1 for q in lit):
            lit.append(p)
        elif len(ghosts) < n_ghosts and all(apart(p, q) > 1 for q in ghosts):
            ghosts.append(p)
    motifs = r.sample(MOTIFS, len(MOTIFS))
    # A taller tower has more rooms than motifs: each extra room repeats one, mirrored, taking
    # the motif whose first room is farthest away.
    picks = list(range(len(motifs)))
    for p in lit[len(motifs) :]:
        spare = [k for k in range(len(motifs)) if k not in picks[len(motifs) :]]
        picks.append(max(spare, key=lambda k: apart(lit[k], p)))

    sills, dark, lamps = P(), P(), P()
    for p in cells:
        x, y = at(p)
        if p != hot:
            sills.rect(x - 4, y + WH, WW + 8, 4)
            (lamps if p in lit else dark).rect(x, y, WW, WH)
    s.fill(sills, SILL)
    s.fill(dark, BG)
    s.fill(lamps, LAMP)
    for p in ghosts:
        sprite(s, pad(CURTAIN), {"#": GHOST}, PX, at(p))
    for i, (p, k) in enumerate(zip(lit, picks)):
        art = fit(motifs[k], flip=i >= len(motifs))
        sprite(s, art, {"#": BG, "+": SHADE, "o": UI_ALT}, PX, at(p))

    x, y = at(hot)
    s.fill(P().rect(x - 4, y + WH, WW + 8, 4), ACCENT_4)
    s.fill(P().rect(x, y, WW, WH), ACCENT)
    sprite(s, CODER, {"#": ACCENT_3, "f": ACCENT_2, "s": ACCENT_4, "l": ACCENT_1}, PX, (x, y))

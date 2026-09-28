"""A Minecraft map item of riverside plains, shaded block by block as the game shades a map, with the player's chunk outlined and the F3 position readout in the game's pixel font."""

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_HI,
    BG_ALT,
    BG_DEEP,
    BLACK,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    by_regime,
    design,
    mix,
)
from walldye.pixel import grid_runs, sprite

type Grid = NDArray[np.int64]
type Field = NDArray[np.float64]

N = 128  # blocks across a scale-0 map
SEA = 62  # water surface y
BX, BZ = 1176, -520  # player block column; Y comes from the terrain
MX, MZ = (BX + 64) // 128 * 128 - 64, (BZ + 64) // 128 * 128 - 64  # map NW corner (vanilla grid)
RIVER = 0.075  # half-width of the river band in |noise|

# MapColor kinds, darkest first, and their three shades. The game multiplies a base colour by
# 180, 220 or 255/255 by slope; here each shade mixes toward BLACK instead, a shallower floor
# than zero, so the steps are larger. Palette order: kind * 3 + tier.
PLANT, GRASS, WATER = 0, 1, 2  # PLANT covers leaves and short grass
BASES = (mix(BG_ALT, UI, 0.6), mix(UI_ALT, UI_HI, 0.15), mix(UI_HI, MUTED, 0.08))
SHADES = tuple(mix(BLACK, base, k) for base in BASES for k in (0.6, 0.82, 1.0))
# On a light screen the ladder runs end to end the other way, so the woods stay the densest
# ink, the river the palest, and slopes facing north still fall into shadow.
TONES = tuple(by_regime(dark, light) for dark, light in zip(SHADES, SHADES[::-1], strict=True))
PAPER, EDGE = UI_ALT, UI  # map_background.png: the paper and its outline

# textures/map/decorations/player.png (8x8), north-up.
PLAYER = """
....#...
...#a#..
..#aWa#.
..#WXW#.
..#WXW#.
..#aWa#.
...###..
"""

# textures/font/ascii.png glyphs the readout uses: rows top-down, trimmed to the glyph width;
# a glyph advances its width plus one, a space four.
FONT = {
    "(": "..#|.#.|#..|#..|#..|.#.|..#",
    ")": "#..|.#.|..#|..#|..#|.#.|#..",
    "-": ".....|.....|.....|#####",
    ".": ".|.|.|.|.|.|#",
    "/": "....#|...#.|...#.|..#..|.#...|.#...|#....",
    "0": ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.",
    "1": "..#..|.##..|..#..|..#..|..#..|..#..|#####",
    "2": ".###.|#...#|....#|..##.|.#...|#...#|#####",
    "3": ".###.|#...#|....#|..##.|....#|#...#|.###.",
    "4": "...##|..#.#|.#..#|#...#|#####|....#|....#",
    "5": "#####|#....|####.|....#|....#|#...#|.###.",
    "6": "..##.|.#...|#....|####.|#...#|#...#|.###.",
    "7": "#####|#...#|....#|...#.|..#..|..#..|..#..",
    "8": ".###.|#...#|#...#|.###.|#...#|#...#|.###.",
    "9": ".###.|#...#|#...#|.####|....#|...#.|.##..",
    ":": ".|.|#|.|.|.|#",
    "B": "####.|#...#|####.|#...#|#...#|#...#|####.",
    "C": ".###.|#...#|#....|#....|#....|#...#|.###.",
    "F": "#####|#....|###..|#....|#....|#....|#....",
    "S": ".####|#....|.###.|....#|....#|#...#|.###.",
    "T": "#####|..#..|..#..|..#..|..#..|..#..|..#..",
    "X": "#...#|.#.#.|..#..|.#.#.|#...#|#...#|#...#",
    "Y": "#...#|.#.#.|..#..|..#..|..#..|..#..|..#..",
    "Z": "#####|....#|...#.|..#..|.#...|#....|#####",
    "[": "###|#..|#..|#..|#..|#..|###",
    "]": "###|..#|..#|..#|..#|..#|###",
    "a": ".....|.....|.###.|....#|.####|#...#|.####",
    "c": ".....|.....|.###.|#...#|#....|#...#|.###.",
    "d": "....#|....#|.##.#|#..##|#...#|#...#|.####",
    "e": ".....|.....|.###.|#...#|#####|#....|.####",
    "f": "..##|.#..|####|.#..|.#..|.#..|.#..",
    "g": ".....|.....|.####|#...#|#...#|.####|....#|####.",
    "h": "#....|#....|#.##.|##..#|#...#|#...#|#...#",
    "i": "#|.|#|#|#|#|#",
    "k": "#...|#...|#..#|#.#.|##..|#.#.|#..#",
    "l": "#.|#.|#.|#.|#.|#.|.#",
    "m": ".....|.....|##.#.|#.#.#|#.#.#|#...#|#...#",
    "n": ".....|.....|####.|#...#|#...#|#...#|#...#",
    "o": ".....|.....|.###.|#...#|#...#|#...#|.###.",
    "r": ".....|.....|#.##.|##..#|#....|#....|#....",
    "s": ".....|.....|.####|#....|.###.|....#|####.",
    "t": ".#.|.#.|###|.#.|.#.|.#.|..#",
    "u": ".....|.....|#...#|#...#|#...#|#...#|.####",
    "v": ".....|.....|#...#|#...#|#...#|.#.#.|..#..",
    "w": ".....|.....|#...#|#...#|#.#.#|#.#.#|.####",
}
LINE = 9  # font rows per readout line, its backing included
PX = 3  # canvas units per font pixel (GUI scale 3)
MARGIN = 72  # readout inset from the top-left corner
GAP = 100  # least space around the map on a landscape screen


def advance(line: str) -> int:
    """Width of `line` in font pixels, counting each glyph's one-pixel trailing gap."""
    return sum(4 if ch == " " else FONT[ch].index("|") + 1 for ch in line)


def readout(lines: list[str]) -> Grid:
    """The lines as a 0/1 pixel grid, `LINE` rows per line."""
    grid = np.zeros((LINE * len(lines), max(map(advance, lines))), np.int64)
    for r, line in enumerate(lines):
        x = 0
        for ch in line:
            if ch == " ":
                x += 4
                continue
            rows = FONT[ch].split("|")
            for j, row in enumerate(rows):
                for i, c in enumerate(row):
                    grid[r * LINE + j, x + i] = c == "#"
            x += len(rows[0]) + 1
    return grid


def terrain(s: Canvas) -> tuple[Grid, Grid]:
    """Top-block heights and MapColor kinds for the map's columns plus one row to the north,
    (N + 1, N) arrays."""
    zs, xs = np.mgrid[0 : N + 1, 0:N]
    wx, wz = MX + xs, MZ - 1 + zs  # world block coordinates

    def fbm(key: int, scale: float, octaves: int) -> Field:
        return 2 * s.noise(key).fbm(wx / scale, wz / scale, octaves=octaves)

    base, fine, river, forest = fbm(21, 45, 3), fbm(4, 9, 2), fbm(9, 95, 2), fbm(33, 32, 2)
    rv = np.abs(river)
    wet = rv < RIVER
    # The river bed deepens toward the band's middle; the banks ease the plains down to it.
    bed = SEA - 1 - np.round(5 * np.minimum(1.0, 2.2 * (1 - rv / RIVER)))
    bank = np.minimum(1.0, (rv - RIVER) / 0.08)
    plain = 64 + base * 5 + fine * 1.2
    ground = np.maximum(SEA + 1, np.round(SEA + 1 + (plain - SEA - 1) * bank))
    h = np.where(wet, bed, ground).astype(np.int64)  # the ground block
    kind = np.where(wet, WATER, GRASS).astype(np.int64)

    # Short grass: patchy PLANT columns one block above the grass block, thicker in the forest.
    rnd = s.rng(5)
    grass = kind == GRASS
    roll = np.array([rnd.random() for _ in range(int(grass.sum()))])
    tall = np.zeros_like(grass)
    tall[grass] = roll < 0.08 + 0.3 * np.maximum(0.0, forest[grass])
    top = h + tall
    kind[tall] = PLANT

    # Oak trees: blob foliage of radius 2, 2, 1, 1 by layer, the top layer's corners always
    # cut and the others' half the time; never in or beside the river.
    taken = np.zeros_like(grass)
    for _ in range(4000):
        i, j = rnd.randrange(N), rnd.randrange(N + 1)
        near = np.s_[max(0, j - 2) : j + 3, max(0, i - 2) : i + 3]
        if rnd.random() > (0.9 if forest[j, i] > 0.45 else 0.02) or taken[near].any():
            continue
        shore = np.s_[max(0, j - 3) : j + 4, max(0, i - 3) : i + 4]
        if kind[j, i] == WATER or (rv[shore] < RIVER + 0.01).any():
            continue
        taken[j, i] = True
        trunk = h[j, i] + 4 + rnd.randrange(3)
        for dy, r in ((-2, 2), (-1, 2), (0, 1), (1, 1)):
            y = trunk + dy
            for dz in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if abs(dx) == r and abs(dz) == r and (dy == 1 or rnd.random() < 0.5):
                        continue
                    a, b = j + dz, i + dx
                    if 0 <= a <= N and 0 <= b < N and y > top[a, b]:
                        top[a, b], kind[a, b] = y, PLANT
    return top, kind


def shading(top: Grid, kind: Grid) -> Grid:
    """Palette indices (1 + kind * 3 + tier) for the map's N x N pixels, as the game's
    MapItem.update shades a scale-0 map: water by its depth, land by its height against the
    block to the north, each with a checkerboard nudge."""
    zs, xs = np.mgrid[1 : N + 1, 0:N]
    odd = (xs + zs) & 1
    here, k = top[1:], kind[1:]
    north = np.where(kind[:-1] == WATER, SEA, top[:-1])
    deep = (SEA - here) * 0.1 + odd * 0.2
    slope = (here - north) + (odd - 0.5) * 0.4
    tier = np.where(
        k == WATER,
        np.select([deep < 0.5, deep > 0.9], [2, 0], 1),
        np.select([slope > 0.6, slope < -0.6], [2, 0], 1),
    )
    return 1 + k * 3 + tier


@design(aspects="any")
def draw(s: Canvas) -> None:
    top, kind = terrain(s)
    lx, lz = BX - MX, BZ - MZ  # the player's column on the map
    assert kind[lz + 1, lx] != WATER
    # feet stand on the grass block, or inside the short grass
    by = int(top[lz + 1, lx]) + int(kind[lz + 1, lx] == GRASS)

    # F3 readout, Java 1.21 defaults; the values come from the marker so they cannot drift.
    region = f"r.{BX >> 9}.{BZ >> 9}.mca"
    lines = [
        f"XYZ: {BX + 0.5:.3f} / {by:.5f} / {BZ + 0.5:.3f}",
        f"Block: {BX} {by} {BZ}",
        f"Chunk: {BX >> 4} {by >> 4} {BZ >> 4} [{(BX >> 4) & 31} {(BZ >> 4) & 31} in {region}]",
        "Facing: north (Towards negative Z) (-180.0 / 0.0)",
        "minecraft:overworld FC: 0",
        f"Section-relative: {BX & 15:02d} {by & 15:02d} {BZ & 15:02d}",
    ]
    backs = P()
    for r, line in enumerate(lines):
        y = MARGIN + r * LINE * PX
        backs.rect(MARGIN - PX, y - PX, (advance(line) + 1) * PX, LINE * PX)
    s.fill(backs, BG_ALT)
    grid_runs(s, readout(lines), [None, MUTED], PX, (MARGIN, MARGIN))
    right = MARGIN + max(map(advance, lines)) * PX  # the readout's right edge

    # Six units per block, or five where a landscape screen is too narrow for the map beside
    # the readout. The map sits right of centre, or below the readout on a portrait screen.
    b = 6 if not s.landscape or right + 2 * GAP + 142 * 6 <= s.w else 5
    c = s.pick(landscape=(0.726, 0.5), portrait=(0.5, 0.56), snap=b)
    origin = c - (N // 2 * b, N // 2 * b)  # the NW corner of the map's content

    art: str = s.data("map_background.txt")
    # its 64 texels span map units -7..135, so the paper shows round the content
    sprite(s, art, {"a": EDGE, "b": PAPER}, 142 * b / 64, origin - (7 * b, 7 * b))
    grid_runs(s, shading(top, kind), [None, *TONES], b, origin)

    cx, cz = (BX >> 4) * 16 - MX, (BZ >> 4) * 16 - MZ
    chunk = P().rect(origin.x + cx * b - 1, origin.y + cz * b - 1, 16 * b + 2, 16 * b + 2)
    s.stroke(chunk, ACCENT, 2)
    # one icon texel per map pixel, the arrow's axis on the player's column
    at = origin + ((lx - 4) * b, (lz - 3) * b)
    sprite(s, PLAYER, {"#": BG_DEEP, "a": ACCENT_2, "W": ACCENT, "X": ACCENT_HI}, b, at)

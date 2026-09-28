"""A block cave in cross-section lit by one floor torch: light floods the air one level dimmer per block, and each exposed rock face takes the level of the air beside it."""

from collections import deque

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    ACCENT_HI,
    BG,
    FG,
    MUTED,
    UI_HI,
    Canvas,
    Colour,
    by_regime,
    design,
    mix,
)
from walldye.pixel import Pixels

CELL = 8  # one texel
TEX = 16  # texels along a block edge
TORCH_LEVEL = 14
# '#' deepslate, 'R' deepslate redstone ore, '.' air, 'T' floor torch
CAVE = """
###########.###
#####R.....####
###.........###
##...........##
#...........###
............R##
#...###T......#
##..R######...#
###.#######..##
"""
BACK = 0.3  # air cells show the back wall one block deeper, in its own shadow
STEPS = 32  # tones between the void and full light
# The texel at full light and top rank; block light leans 8% towards ACCENT_HI.
LIT_DARK = mix(mix(UI_HI, MUTED, 0.3), ACCENT_HI, 0.08)
# On light themes the page is the light and the ink the dark: the void takes UNLIT_LIGHT and
# full light rises to the page. The air there gets its own ramp, steeper than BACK and with
# the back wall's grain damped, so the falloff shows and the rock faces still stand apart.
UNLIT_LIGHT = UI_HI
LIT_LIGHT = mix(BG, ACCENT_HI, 0.04)
AIR_TOP = 0.5  # light-theme air at full light, as a fraction of the way to LIT_LIGHT
AIR_GRAIN = 0.3  # light-theme air: how far the lowest texture rank dips below the top one

# after the game's deepslate texture: luminance ranked 0..4
DEEPSLATE = """
4322221133322122
2100111123221121
3343322000011011
1232211123443332
0122111233343321
4423220233232223
4332201122110012
3211113433210122
2121112432321112
1100222322121001
3232122110012244
3321344421211243
3211243332111233
1110023321010011
4433211014322334
4432322024332233
"""
# after the game's deepslate redstone ore: texels that differ from deepslate, rim a to core h
ORE_ART = """
................
................
.....bba........
...bbddda.......
...edefged......
....efhfc...efc.
.....ccc....cc..
.bba......bb....
bfgda....dedegf.
.dfc.......ghfc.
.cc.........cc..
...abba.........
..adfefd...ef...
...cgh..........
....cc..........
................
"""
ORE_RAMP = (
    ACCENT_7,
    ACCENT_6,
    ACCENT_4,
    ACCENT_3,
    ACCENT_2,
    ACCENT,
    mix(ACCENT, ACCENT_HI, 0.5),
    ACCENT_HI,
)
ORE_RANK = {ch: i - 1 for i, ch in enumerate(".abcdefgh")}  # -1: deepslate shows through
# after the game's torch texture, columns 7-8 and rows 6-15: the flame on top, then the stick
TORCH = """
ha
w4
45
s6
4t
46
s6
57
47
57
"""
# Dark first; on light themes the low accent rungs fade into the page, so the stick inks darker.
TORCH_INK = {
    "w": by_regime(mix(ACCENT_HI, FG, 0.45), ACCENT_2),
    "h": by_regime(ACCENT_HI, ACCENT),
    "a": by_regime(ACCENT, ACCENT_1),
    "4": by_regime(ACCENT_4, mix(ACCENT_HI, MUTED, 0.6)),
    "5": by_regime(ACCENT_5, mix(ACCENT_HI, MUTED, 0.4)),
    "6": by_regime(ACCENT_6, mix(ACCENT_HI, MUTED, 0.2)),
    "7": by_regime(ACCENT_7, ACCENT_HI),
    "s": by_regime(mix(ACCENT_4, ACCENT_5, 0.3), mix(ACCENT_HI, MUTED, 0.5)),
    "t": by_regime(mix(ACCENT_6, ACCENT_7, 0.6), mix(ACCENT_HI, MUTED, 0.12)),
}


def brightness(level: float) -> float:
    """Rendered brightness of a light level, on a lightmap-style curve that sinks faster than
    linear toward the dark end, normalised so that TORCH_LEVEL gives 1."""

    def f(v: float) -> float:
        return (v / 15) / (3 - 2 * v / 15)

    return f(level) / f(TORCH_LEVEL)


GLOW = np.array([brightness(v) for v in range(TORCH_LEVEL + 1)])
TEXTURE = np.array([[int(ch) for ch in row] for row in DEEPSLATE.split()])
ORE = np.array([[ORE_RANK[ch] for ch in row] for row in ORE_ART.split()])


def texel(air: bool, level: int, rank: int) -> Colour | None:
    """A rock-face or air texel at a light level and texture rank; None where the dark render
    rounds it to the void."""
    grain = 0.45 + 0.55 * rank / 4
    t = round(GLOW[level] * (BACK if air else 1.0) * grain * STEPS) / STEPS
    if t == 0:
        return None
    lit = AIR_TOP * GLOW[level] * (1 - AIR_GRAIN * (1 - rank / 4)) if air else t
    return by_regime(mix(BG, LIT_DARK, t), mix(UNLIT_LIGHT, LIT_LIGHT, round(lit * STEPS) / STEPS))


def shades() -> tuple[list[Colour], NDArray[np.int64]]:
    """The distinct texel colours, and an (air, level, rank) table of their palette indices
    counted from 1, with 0 for the void."""
    index: dict[Colour, int] = {}
    table = np.zeros((2, TORCH_LEVEL + 1, 5), dtype=np.int64)
    for a, lv, rk in np.ndindex(table.shape):
        c = texel(bool(a), lv, rk)
        if c is not None:
            table[a, lv, rk] = index.setdefault(c, len(index) + 1)
    return list(index), table


# Palette: 0 the void, the texel colours, ore texels by (level, rank), then the torch.
TEXELS, SHADE = shades()
ORE_BASE = len(TEXELS) + 1
TORCH_BASE = ORE_BASE + len(GLOW) * len(ORE_RAMP)
PALETTE = (
    None,
    *TEXELS,
    *[
        by_regime(mix(BG, c, 0.35 + 0.65 * g), mix(UNLIT_LIGHT, c, 0.35 + 0.65 * g))
        for g in GLOW
        for c in ORE_RAMP
    ],
    *[TORCH_INK[ch] for ch in TORCH_INK],
)
TORCH_KEY = {ch: TORCH_BASE + i for i, ch in enumerate(TORCH_INK)}


def flood(air: NDArray[np.bool_], start: tuple[int, int], level: int) -> NDArray[np.int64]:
    """Block light on a (rows, cols) grid: `level` at `start`, one less per 4-neighbour step
    through `air` cells, and 0 in solid cells and wherever it has run out."""
    rows, cols = air.shape
    light = np.zeros(air.shape, dtype=np.int64)
    light[start] = level
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            inside = 0 <= nr < rows and 0 <= nc < cols
            if inside and air[nr, nc] and light[nr, nc] < light[r, c] - 1:
                light[nr, nc] = light[r, c] - 1
                queue.append((nr, nc))
    return light


def texels[T: np.generic](a: NDArray[T]) -> NDArray[T]:
    """A (rows, cols) per-block array blown up to one value per texel."""
    return np.repeat(np.repeat(a, TEX, axis=0), TEX, axis=1)


@design(bg=by_regime(BG, UNLIT_LIGHT))
def draw(s: Canvas) -> None:
    cave = np.array([list(row) for row in CAVE.split()])
    rows, cols = cave.shape
    air = np.isin(cave, (".", "T"))
    tr, tc = (int(v[0]) for v in np.nonzero(cave == "T"))
    light = flood(air, (tr, tc), TORCH_LEVEL)

    # A rock face takes the brightest of its four neighbours; solid cells hold 0 light.
    pad = np.pad(light, 1)
    face = np.maximum.reduce([pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]])
    level = np.where(air, light, face)

    grid = SHADE[texels(air).astype(np.int64), texels(level), np.tile(TEXTURE, (rows, cols))]
    rank = np.tile(ORE, (rows, cols))
    ore = texels(cave == "R") & (rank >= 0)
    grid[ore] = (ORE_BASE + texels(level) * len(ORE_RAMP) + rank)[ore]

    # Each block's middle tone underneath, so the anti-aliased seams between texels at
    # fractional scales show that rather than the void.
    under = Pixels(cols, rows, PALETTE)
    under.grid[:] = SHADE[air.astype(np.int64), level, 2]
    under.draw(s, TEX * CELL)

    # the cave is taller than the screen: its bottom row runs off the lower edge
    px = Pixels(cols * TEX, s.h // CELL, PALETTE)
    px.grid[:] = grid[: px.rows]
    px.stamp(TORCH, tc * TEX + 7, tr * TEX + 6, TORCH_KEY)
    px.draw(s, CELL)

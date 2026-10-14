"""A pixel-art campfire under a sparse starfield, its glow dithered onto the ground around it."""

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    ACCENT_8,
    ACCENT_HI,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Rect,
    by_regime,
    design,
)
from walldye.field import falloff
from walldye.pixel import Pixels

PX = 7  # one art pixel
LOG = 19  # log length in cells
STAR_SKY = 613  # sky cells per star: 30 stars over the upper half of a 16:9 screen
# The fire base's default place: a little left of center and low on a landscape screen,
# centered in the lower third on a portrait one.
LANDSCAPE, PORTRAIT = (0.4375, 0.765), (0.5, 0.7)
# Cells around the fire base that hold the fire and its glow: the pool spans 70 to either side
# and sinks 11 rows below, the last spark rises 53.
LEFT, UP, RIGHT, DOWN = 70, 54, 70, 12
TILE = 64  # every dither mask repeats within 64 cells

# Art characters and their paints; grid index 0 is the empty ground.
INKS = (
    ("g", ACCENT_8),  # glow ramp, faintest first
    ("v", ACCENT_7),
    ("w", ACCENT_6),
    ("x", ACCENT_5),
    ("d", ACCENT_3),  # flame and embers, outside in
    ("r", ACCENT_1),
    ("o", ACCENT),
    ("y", by_regime(ACCENT_HI, ACCENT_3)),  # on paper the hottest core is the palest
    ("t", by_regime(UI_ALT, UI)),  # log: lit top, body and shaded underside
    ("b", by_regime(UI, UI_ALT)),
    ("u", by_regime(BG_ALT, UI_HI)),
    ("L", BG_ALT),  # stars, faintest first
    ("l", UI),
    ("m", UI_ALT),
)
PALETTE = (None, *(p for _, p in INKS))
KEY = {ch: i + 1 for i, (ch, _) in enumerate(INKS)}
GLOW = (0, KEY["g"], KEY["v"], KEY["w"], KEY["x"])

FLAME = """
..........r..........
..........r..........
.........rr..........
.........rr..........
.........rrr.........
........rrrr.........
........rror.....r...
...r....rror....rr...
...r...rroorr...rr...
...rr..rroorr..rro...
...rr..rooorr..roo...
...rrr.rooooorrroo...
....rrrroooooorroor..
....rrooooyoooooorr..
....rroooyyyooooorr..
...rroooyyyyyoooorr..
...rrooyyyyyyyooorr..
..rrooyyyyyyyyyoorr..
..rrooyyyyyyyyyoorr..
..rroooyyyyyyyooorr..
..rrroooyyyyyoooorr..
...rrrooooooooorrr...
....rrrrrooooorrrr...
......rrrrrrrrrr.....
"""

EMBERS = """
..drd..
.drord.
drroyrd
"""

# Sparks on the draft as (dx, rise, character) in cells: bunched near the flame, dimmer as they rise.
SPARKS = ((-1, 29, "o"), (2, 34, "r"), (-3, 42, "d"), (-6, 53, "x"))


def log(px: Pixels, x0: int, y0: int, dx: int) -> None:
    """Paint a log as a 2:1 pixel line three rows thick (lit top, body, shaded underside),
    rising away from column x0, row y0 towards the side `dx` (+1 or -1) points."""
    k = np.arange(LOG)
    for t, ch in enumerate("tbu"):
        px.grid[y0 - k // 2 + t, x0 + dx * k] = KEY[ch]


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Stars: sparse pixels across the upper half, one in three brighter, the first three as
    # tiny crosses.
    cols, rows = -(-s.w // PX), -(-s.h // PX)
    sky = Pixels(cols, rows, PALETTE)
    r = s.rng(5)
    for k in range(round((cols - 16) * (rows // 2 - 6) / STAR_SKY)):
        x, y = r.randrange(8, cols - 8), r.randrange(6, rows // 2)
        if k < 3:
            sky.grid[y, x - 1 : x + 2] = KEY["L"]
            sky.grid[y - 1 : y + 2, x] = KEY["L"]
            sky.grid[y, x] = KEY["m"]
        else:
            sky.grid[y, x] = KEY["L" if k % 3 else "l"]
    sky.draw(s, PX)

    base = s.pick(landscape=LANDSCAPE, portrait=PORTRAIT, snap=PX)
    # The grid's corner sits whole mask tiles from the fire's default cell, so there the dither
    # lines up with the screen's corner.
    home = LANDSCAPE if s.landscape else PORTRAIT
    fx, fy = round(home[0] * s.w / PX), round(home[1] * s.h / PX)
    x0, y0 = LEFT + (fx - LEFT) % TILE, UP + (fy - UP) % TILE
    px = Pixels(x0 + RIGHT, y0 + DOWN, PALETTE)
    ys, xs = np.mgrid[-y0:DOWN, -x0:RIGHT]

    # Ground glow: a wide, shallow pool that hugs the ground, squashed harder above the fire
    # base than below, in four ordered-dither steps.
    dy = ys - 3
    pool = np.hypot(xs / 70, dy / np.where(dy < 0, 4, 9))
    px.dither(0.8 * falloff(pool, 1, 1.6), GLOW, method="bayer", matrix=4)
    # Air glow: the faintest halo around the flames, in the gaps the pool leaves.
    halo = 0.3 * falloff(np.hypot(xs, (ys + 12) * 1.2), 30, 2)
    px.dither(halo, (0, KEY["g"]), method="bluenoise", rng=s.np_rng(3), where=px.grid == 0)

    # The logs cross just under the flame base; embers fill the V beneath the crossing.
    log(px, x0 - 13, y0 + 6, 1)
    log(px, x0 + 13, y0 + 6, -1)
    px.stamp(EMBERS, x0 - 3, y0 + 5, KEY)
    px.stamp(FLAME, x0 - 10, y0 - 23, KEY)
    for dx, rise, ch in SPARKS:
        px.grid[y0 - rise, x0 + dx] = KEY[ch]
    ink = Rect(-LEFT * PX, -UP * PX, (LEFT + RIGHT) * PX, (UP + DOWN) * PX)
    fire = Rect(-13 * PX, -23 * PX, 27 * PX, 32 * PX)  # the flame and the logs
    with s.motif(base, ink, handle=fire, cell=PX):
        px.draw(s, PX, (-x0 * PX, -y0 * PX))

"""A pixel-art rocket clearing its launch tower, the flame lighting the tops of a low bank of smoke."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    ACCENT_HI,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    by_regime,
    design,
)
from walldye.pixel import Pixels

CELL = 6
# Palette indices; 0 is the empty sky. The hull tones by step, then the flame from tail to core.
SHADE, FAINT, LINE, HULL, EDGE = 1, 2, 3, 4, 5
EMBER, WARM, TAIL, BODY, FLAME, CORE, BAND = 6, 7, 8, 9, 10, 11, 12
PALETTE = (
    None,
    by_regime(BG_DEEP, UI_HI),  # seams and window stay darker than the hull on paper too
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    ACCENT_6,
    ACCENT_5,
    ACCENT_3,
    ACCENT_1,
    ACCENT,
    ACCENT_HI,
    ACCENT_7,
)
KEY = {"k": SHADE, "d": FAINT, "b": LINE, "a": HULL, "h": EDGE, "r": BAND}

ROCKET = """
......hd......
......hd......
.....habd.....
.....habd.....
....haabbd....
....haabbd....
....haabbd....
...haaabbbd...
...haaabbbd...
...kkkkkkkk...
...haaabbbd...
...haakkbbd...
...haakkbbd...
...haaabbbd...
...hrrrrrrd...
...haaabbbd...
...haaabbbd...
...haaabbbd...
...haaabbbd...
...kkkkkkkk...
...haaabbbd...
...haaabbbd...
...haaabbbd...
...haaabbbd...
...haaabbbd...
..bhaaabbbdd..
..bhaaabbbdd..
.bbhaaabbbddd.
.bbhaaabbbddd.
bbbhaaabbbdddd
bb.kkkkkkkk.dd
b...abbbdd...d
...aabbbddd...
""".strip("\n").split("\n")
AXIS = 6  # the flame's column within the art
LIFT = 80  # rows from the rocket's nose down to the ground line
TOWER = 82  # tower height in rows; its top is two rows above the nose
# Flame rows from the nozzle down, as ((half-width, core, body, edge), rows): a glinting bulb
# that steps down the accent ramp as it narrows into the smoke.
FLAME_ROWS = (
    ((1, CORE, FLAME, FLAME), 2),
    ((2, CORE, FLAME, BODY), 8),
    ((2, FLAME, BODY, TAIL), 3),
    ((1, FLAME, BODY, BODY), 9),
    ((1, BODY, TAIL, TAIL), 8),
    ((0, TAIL, TAIL, TAIL), 6),
)
# Smoke rows, back first: (puff spacing, extra radius at the flame, base radius, lift).
PUFFS = ((8, 7.5, 2.2, 0.9), (9, 4, 2.4, 0.55))
# Stars as cells of a 320-column sky 150 rows deep (16:9), scaled to the sky of any screen.
STARS = (
    (40, 20),
    (88, 44),
    (131, 12),
    (160, 60),
    (250, 25),
    (290, 70),
    (305, 18),
    (20, 95),
    (70, 110),
    (275, 110),
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = s.w // CELL, s.h // CELL
    px = Pixels(cols, rows, PALETTE)
    # the flame's column and the ground row: right of centre on a landscape screen, low on a
    # portrait one with the sky above for the clock
    base = s.pick(landscape=(0.675, 5 / 6), portrait=(0.56, 0.8), snap=CELL)
    fx, ground = int(base.x) // CELL, int(base.y) // CELL
    rx, ry = fx - AXIS, ground - LIFT
    j, i = np.mgrid[0:rows, 0:cols]

    # Launch tower left of the rocket: two rails, a zigzag brace and three crossbars.
    tx, tw, top = rx - 14, 6, ground - TOWER
    y = np.arange(top, ground)
    seg, k = np.divmod(y - top, 4)
    px.grid[y, np.where(seg % 2 == 0, tx + 1 + k, tx + tw - 2 - k)] = FAINT
    px.grid[top:ground, [tx, tx + tw - 1]] = LINE
    px.grid[[top, top + 16, top + 32], tx : tx + tw] = LINE
    px.grid[top - 3 : top, tx + 2] = LINE

    row = ry + len(ROCKET)  # the nozzle
    for (half, core, body, edge), n in FLAME_ROWS:
        for _ in range(n):
            for x in range(fx - half, fx + half + 1):
                d = abs(x - fx)
                px.grid[row, x] = core if d == 0 else edge if d == half else body
            row += 1

    # Smoke: two rows of puffs painted back to front, swelling towards the flame. Bodies stay
    # faint; a front puff's top edge gets a one-cell lit cap, WARM (ACCENT_5) on the upper
    # arc of the puffs right under the flame.
    rng = s.np_rng(5)
    owner = np.full((rows, cols), -1)
    warm: list[bool] = []
    crown: list[float] = []
    for back, (step, big, small, lift) in enumerate(PUFFS):
        for x0 in np.arange(fx - 42 + back * 4, fx + 45, step):
            x = x0 + rng.uniform(-1, 1)
            r = small + big * math.exp(-(((x - fx) / 26) ** 2)) * rng.uniform(0.9, 1.05)
            cy = ground - r * lift
            disc = ((i + 0.5 - x) ** 2 + (j + 0.5 - cy) ** 2 < r * r) & (j < ground)
            owner[disc] = len(warm)
            warm.append(back == 0 and bool(abs(x - fx) < 10))
            crown.append(cy - r * 0.45)
    puff = owner >= 0
    cap = puff & (np.roll(owner, 1, 0) < owner)
    near = sum(np.roll(np.roll(cap, a, 0), b, 1) for a in (-1, 0, 1) for b in (-1, 1))
    cap &= near > 0  # a lone cap cell is a puff barely peeking out; drop it
    hot = puff & np.array(warm)[owner] & (j < np.array(crown)[owner])
    px.grid[puff] = FAINT
    px.grid[cap] = np.where(hot, WARM, LINE)[cap]
    px.grid[hot & ~cap & np.roll(cap, 1, 0)] = EMBER

    horizon = px.grid[ground]
    horizon[horizon == 0] = LINE
    px.stamp(ROCKET, rx, ry, KEY)

    for x, y in STARS:
        px.grid[round(y * ground / 150), round(x * cols / 320)] = LINE

    px.draw(s, CELL)

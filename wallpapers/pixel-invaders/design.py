"""A Space Invaders formation with one crab diving out of it, drawn on a single pixel-art grid."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    BG_ALT,
    UI,
    Canvas,
    Rng,
    design,
    mix,
)
from walldye.pixel import Pixels

PX = 6  # one sprite pixel; every position below is in these cells
DX, DY = 16, 10  # formation pitch

SQUID = (
    "...##...|..####..|.######.|##.##.##|########|..#..#..|.#.##.#.|#.#..#.#",
    "...##...|..####..|.######.|##.##.##|########|.#.##.#.|#......#|.#....#.",
)
CRAB = (
    "..#.....#..|...#...#...|..#######..|.##.###.##.|###########|#.#######.#|#.#.....#.#|...##.##...",
    "..#.....#..|#..#...#..#|#.#######.#|###.###.###|###########|.#########.|..#.....#..|.#.......#.",
)
OCTO = (
    "....####....|.##########.|############|###..##..###|############|...##..##...|..##.##.##..|##........##",
    "....####....|.##########.|############|###..##..###|############|..###..###..|.##..##..##.|..##....##..",
)
CANNON = "......#......|.....###.....|.....###.....|.###########.|#############|#############|#############|#############"
ROWS = (SQUID, CRAB, CRAB, OCTO, OCTO)

PALETTE = (
    None,
    BG_ALT,
    mix(BG_ALT, UI, 0.5),
    mix(BG_ALT, UI, 0.6),
    UI,
    ACCENT_5,
    ACCENT_4,
    ACCENT_3,
    ACCENT_2,
    ACCENT,
)
FAR, MID, SHIELD, NEAR, DIVER = 1, 2, 3, 4, 9
ROW_TONE = (FAR, MID, MID, NEAR, NEAR)  # the formation fades toward the back
TRAIL = (5, 6, 7, 8)  # the accent ladder along the dive, oldest dot first


def art(a: str) -> list[str]:
    return a.split("|")


def bunker(rng: Rng) -> NDArray[np.bool_]:
    """A 22x16 arch shield mask with 2-4 craters: the first above the arch (the player's
    shots), the rest bitten from the top edge (bombs)."""
    y, x = np.mgrid[0:16, 0:22]
    corner = (y < 4) & ((x < 4 - y) | (x > 17 + y))
    arch = ((y >= 12) & (x >= 6) & (x <= 15)) | ((y >= 11) & (x >= 7) & (x <= 14))
    solid = ~(corner | arch)
    for b in range(rng.randint(2, 4)):
        cx, cy, rad = (
            (rng.randrange(3, 19), rng.choice((0, 1)), rng.uniform(1.6, 2.6))
            if b
            else (rng.randrange(8, 14), 10, 2.2)
        )
        for j in range(16):
            for i in range(22):
                if math.hypot(i - cx, (j - cy) * 1.2) < rad + rng.uniform(-0.6, 0.6):
                    solid[j, i] = False
    return solid


def trail(x: int, y: int, dive: int) -> list[tuple[int, int]]:
    """The peel-out path as 8-way moves ending `dive` steps straight down: 3 cells per axis
    step and 2 per axis on a diagonal, so the dots read evenly spaced."""
    dots = [(x, y)]
    for dx, dy, n in ((1, 0, 5), (1, -1, 3), (1, 0, 9), (1, 1, 3), (0, 1, dive), (-1, 1, 3)):
        step = 2 if dx and dy else 3
        for _ in range(n):
            x, y = x + dx * step, y + dy * step
            dots.append((x, y))
    return dots


@design(aspects="any")
def draw(s: Canvas) -> None:
    px = Pixels(s.w // PX, s.h // PX, PALETTE)
    w, h = px.cols, px.rows

    # 8 columns at 16:9, 11 (the arcade's count) on ultrawide, 5 on a phone; the formation and
    # the diver's sideways excursion together sit a third of the way into the free width
    cols = max(5, min(11, round(w / 40)))
    reach = (cols - 1) * DX + 60
    x0 = round((w - reach) * 0.34)
    y0 = round(h * (1 / 6 if s.landscape else 0.2))
    gap = (1, cols - 1)  # (row, col) the diver left
    slot = (x0 + gap[1] * DX + 5, y0 + gap[0] * DY + 3)

    for j, frames in enumerate(ROWS):
        for c in range(cols):
            if (j, c) != gap:
                a = art(frames[(j + c) % 2])
                px.stamp(a, x0 + c * DX + (12 - len(a[0])) // 2, y0 + j * DY, {"#": ROW_TONE[j]})

    # the player's end sits on the bottom edge; shields repeat out from the cannon while they
    # fit, with the cannon's own slot left open for the shot
    floor, margin = h - 19, 20
    rng = s.rng(4)
    for k in (-3, -2, -1, 1):
        bx = slot[0] + k * 50 - 11
        if margin <= bx and bx + 22 <= w - margin:
            px.grid[floor - 32 : floor - 16, bx : bx + 22][bunker(rng)] = SHIELD
    px.stamp(art(CANNON), slot[0] - 6, floor - 10, {"#": NEAR})
    px.grid[floor - 24 : floor - 21, slot[0]] = NEAR  # the shot, up the diver's empty column
    px.grid[floor, margin : w - margin] = FAR

    # the crab lands a little under halfway down on every screen, so tall ones get a longer dive;
    # its top row ends up 10 cells below the slot plus the dive's 3-cell steps
    dive = max(10, round((h * 0.46 - slot[1] - 10) / 3))
    dots = trail(*slot, dive)
    for k, (x, y) in enumerate(dots):
        px.grid[y, x] = TRAIL[k * len(TRAIL) // len(dots)]
    px.stamp(art(CRAB[0]), dots[-1][0] - 8, dots[-1][1] + 4, {"#": DIVER})

    px.draw(s, PX)

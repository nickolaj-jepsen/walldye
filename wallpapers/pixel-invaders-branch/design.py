"""A Space Invaders formation with one crab diving out of it: pixel-art sprites and a stepped dot trail."""

import math

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    BG_ALT,
    UI,
    Canvas,
    P,
    Rng,
    Vec,
    design,
    mix,
)
from walldye.pixel import sprite

PX = 6  # one sprite pixel
DX, DY = 16 * PX, 10 * PX  # formation pitch

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
FORMATION = (BG_ALT, mix(BG_ALT, UI, 0.5), mix(BG_ALT, UI, 0.5), UI, UI)  # fades toward the back
TRAIL = (ACCENT_5, ACCENT_4, ACCENT_3, ACCENT_2)  # the dive's dots, oldest first
LAND = 0.48  # the diver's height as a fraction of the screen


def art(a: str) -> list[str]:
    return a.split("|")


def bunker(rng: Rng) -> list[str]:
    """A 22x16 arch shield: bomb craters bitten from the top edge, one shot-hole above the arch."""
    bites = [(rng.randrange(8, 14), 10, 2.2)]
    bites += [
        (rng.randrange(3, 19), rng.choice((0, 1)), rng.uniform(1.6, 2.6))
        for _ in range(rng.randint(1, 3))
    ]
    rows: list[str] = []
    for y in range(16):
        row = ""
        for x in range(22):
            corner = y < 4 and (x < 4 - y or x > 17 + y)
            arch = y >= 12 and 6 <= x <= 15 or y >= 11 and 7 <= x <= 14
            hit = any(
                math.hypot(x - cx, (y - cy) * 1.2) < rad + rng.uniform(-0.6, 0.6)
                for cx, cy, rad in bites
            )
            row += "." if corner or arch or hit else "#"
        rows.append(row)
    return rows


def trail(start: Vec, dive: int) -> list[Vec]:
    """The dots of the peel-out path as 8-way grid moves, `dive` steps straight down: 3 PX
    per axis step and 2 PX per axis on a diagonal, so the dots read evenly spaced."""
    dots = [start]
    for dx, dy, n in ((1, 0, 5), (1, -1, 3), (1, 0, 9), (1, 1, 3), (0, 1, dive), (-1, 1, 3)):
        step = (2 if dx and dy else 3) * PX
        for _ in range(n):
            dots.append(dots[-1] + (dx * step, dy * step))
    return dots


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Columns follow the width (8 at 16:9, 5 on a phone, the arcade's 11 at 32:9); the group, the
    # formation plus the diver's sideways excursion, sits a little left of centre so the dive
    # has room.
    cols = max(5, min(11, round(s.w / (40 * PX))))
    reach = (cols - 1) * DX + 60 * PX
    # snapped to whole cells: a fractional sprite origin blurs every pixel edge
    top_left = Vec(round((s.w - reach) * 0.35 / PX) * PX, round(s.h / 6 / PX) * PX)
    gap = (1, cols - 1)  # (row, col) the diver left
    slot = top_left + (gap[1] * DX + 5 * PX, gap[0] * DY + 3 * PX)

    for j, frames in enumerate(ROWS):
        for c in range(cols):
            if (j, c) != gap:
                a = art(frames[(j + c) % 2])
                at = top_left + (c * DX + (12 - len(a[0])) // 2 * PX, j * DY)
                sprite(s, a, {"#": FORMATION[j]}, PX, at)

    # the player's end is pinned to the bottom edge; shields repeat out from the cannon while
    # they fit, leaning left so the space under the diver stays quiet. Every shield takes its
    # craters from the stream whether or not it fits, so each one looks the same on every screen.
    floor, margin = s.h - 19 * PX, 20 * PX
    rng = s.rng(4)
    for k in (-2, -1, 1, -3):
        bx = slot.x + k * 50 * PX
        shield = bunker(rng)
        if margin <= bx - 11 * PX and bx + 11 * PX <= s.w - margin:
            sprite(s, shield, {"#": mix(BG_ALT, UI, 0.6)}, PX, (bx - 11 * PX, floor - 32 * PX))
    sprite(s, art(CANNON), {"#": UI}, PX, (slot.x - 6 * PX, floor - 10 * PX))
    s.fill(P().rect(slot.x, floor - 24 * PX, PX, 3 * PX), UI)  # the shot, up the diver's column
    s.fill(P().rect(margin, floor, s.w - 2 * margin, PX), BG_ALT)

    # the crab's centre lands just under halfway down, 14 PX below the slot plus 3 PX per dive
    # step, so taller screens get a longer dive
    dive = max(10, round((LAND * s.h - slot.y - 14 * PX) / (3 * PX)))
    dots = trail(slot, dive)
    with s.buckets(TRAIL, "fill") as b:
        for k, (x, y) in enumerate(dots):
            b[k * len(TRAIL) // len(dots)].rect(x, y, PX, PX)
    sprite(s, art(CRAB[0]), {"#": ACCENT}, PX, dots[-1] + (-8 * PX, 4 * PX))

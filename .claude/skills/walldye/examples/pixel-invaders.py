"""A Space Invaders formation with one accent crab diving out of it: sprite() pixel art and a stepped dot trail."""

import math

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    BG_ALT,
    UI,
    H,
    W,
    mix,
    rng,
    sprite,
)

ASPECTS = ["any"]

U = min(W, H) / 1080  # short-side unit: sizes stay constant relative to the screen's short edge
PX = 6 * U
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
TONES = (
    BG_ALT,
    mix(BG_ALT, UI, 0.5),
    mix(BG_ALT, UI, 0.5),
    UI,
    UI,
)  # formation fades toward the back


def art(a):
    return a.split("|")


def bunker(r):
    """22x16 arch shield: bomb craters bitten from the top edge, one shot-hole above the arch."""
    bites = [(r.randrange(8, 14), 10, 2.2)]
    bites += [
        (r.randrange(3, 19), r.choice((0, 1)), r.uniform(1.6, 2.6)) for _ in range(r.randint(1, 3))
    ]
    rows = []
    for y in range(16):
        row = ""
        for x in range(22):
            corner = y < 4 and (x < 4 - y or x > 17 + y)
            arch = y >= 12 and 6 <= x <= 15 or y >= 11 and 7 <= x <= 14
            hit = any(
                math.hypot(x - cx, (y - cy) * 1.2) < rad + r.uniform(-0.6, 0.6)
                for cx, cy, rad in bites
            )
            row += "." if corner or arch or hit else "#"
        rows.append(row)
    return rows


def trail(x, y, dive):
    """Peel-out path as 8-way grid moves; 3*PX per axis step, 2*PX+2*PX per diagonal, so dots read evenly spaced."""
    dots = [(x, y)]
    for dx, dy, n in ((1, 0, 5), (1, -1, 3), (1, 0, 9), (1, 1, 3), (0, 1, dive), (-1, 1, 3)):
        step = (2 if dx and dy else 3) * PX
        for _ in range(n):
            x, y = x + dx * step, y + dy * step
            dots.append((x, y))
    return dots


def draw(s):
    # Columns follow the width (8 at 16:9, 10 at 21:9, 5 on a phone); the whole group, formation
    # plus the diver's sideways excursion, sits a little left of centre so the dive has room.
    cols = max(5, min(11, round(W / (40 * PX))))
    reach = (cols - 1) * DX + 60 * PX
    # Snapped to whole cells: a fractional sprite origin blurs every pixel edge.
    x0, y0 = round((W - reach) * 0.35 / PX) * PX, round(H / 6 / PX) * PX
    gap = (1, cols - 1)  # (row, col) the diver left
    slot = x0 + gap[1] * DX + 5 * PX, y0 + gap[0] * DY + 3 * PX

    for j, frames in enumerate(ROWS):
        for c in range(cols):
            if (j, c) != gap:
                a = art(frames[(j + c) % 2])
                sprite(
                    s, a, {"#": TONES[j]}, PX, x0 + c * DX + (12 - len(a[0])) // 2 * PX, y0 + j * DY
                )

    # the player's end is pinned to the bottom edge; shields repeat out from the cannon while they fit,
    # leaning left so the space under the diver stays quiet
    floor, margin = H - 19 * PX, 20 * PX
    r = rng(4)
    for k in (-3, -2, -1, 1):
        bx = slot[0] + k * 50 * PX
        if margin <= bx - 11 * PX and bx + 11 * PX <= W - margin:
            sprite(s, bunker(r), {"#": mix(BG_ALT, UI, 0.6)}, PX, bx - 11 * PX, floor - 32 * PX)
    sprite(s, art(CANNON), {"#": UI}, PX, slot[0] - 6 * PX, floor - 10 * PX)
    s.rect(
        slot[0], floor - 24 * PX, PX, 3 * PX, fill=UI
    )  # the shot, aimed up the diver's empty column
    s.rect(margin, floor, W - 2 * margin, PX, fill=BG_ALT)

    # taller screens get a longer dive, so the crab still lands mid-field
    dots = trail(*slot, dive=round(10 * H / min(W, H)))
    tones = (ACCENT_5, ACCENT_4, ACCENT_3, ACCENT_2)
    for k, (x, y) in enumerate(dots):
        s.rect(x, y, PX, PX, fill=tones[k * 4 // len(dots)])
    x, y = dots[-1]
    sprite(s, art(CRAB[0]), {"#": ACCENT}, PX, x - 8 * PX, y + 4 * PX)

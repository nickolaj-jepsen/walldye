"""Nees' Schotter on its side: square outlines whose random jitter and tilt grow column by column, until one escapes."""

import math

from walldye import ACCENT, ACCENT_6, UI, UI_ALT, P, rng

COLS, ROWS, PITCH, SIDE = 29, 9, 50, 46
X0, Y0 = 190, 285
AX, AY = 1775, 845
# the three strays leave holes at the band's corner and trail towards the accent, gaps widening
STRAY_DIR, STRAY_GAPS, STRAY_ROT = (0.55, 0.835), (58, 72, 90), (20, 28, 35)


def square(cx, cy, a, side=SIDE):
    h, c, s = side / 2, math.cos(a), math.sin(a)
    return [
        (cx + x * c - y * s, cy + x * s + y * c) for x, y in ((-h, -h), (h, -h), (h, h), (-h, h))
    ]


def draw(s):
    r = rng(1968)
    crisp, faded = P(), P()
    ux, uy = STRAY_DIR
    placed, dist = [], 0
    for gap, rot in zip(reversed(STRAY_GAPS), reversed(STRAY_ROT)):
        dist += gap
        placed.append((AX - ux * dist, AY - uy * dist))
        faded.poly(square(*placed[-1], math.radians(rot)), closed=True)
    for i in range(COLS):
        t = max(0.0, (i - 6) / (COLS - 7)) ** 1.6
        for j in range(ROWS):
            if (COLS - 1 - i) + (ROWS - 1 - j) < 2:
                continue
            gx, gy = X0 + i * PITCH + SIDE / 2, Y0 + j * PITCH + SIDE / 2
            # resample jitter that would stack a square on a neighbour, or crowd the three strays
            while True:
                cx, cy = gx + r.gauss(0, t * 18), gy + r.gauss(0, t * 18)
                if all(
                    math.hypot(cx - px, cy - py) > (24 if k >= 3 else 44)
                    for k, (px, py) in enumerate(placed)
                ):
                    break
            placed.append((cx, cy))
            (faded if t > 0.6 else crisp).poly(
                square(cx, cy, math.radians(r.uniform(-1, 1) * t * 50)), closed=True
            )
    s.path(crisp, fill="none", stroke=UI_ALT, stroke_width=2, stroke_linejoin="round")
    s.path(faded, fill="none", stroke=UI, stroke_width=2, stroke_linejoin="round")
    s.path(
        P().poly(square(AX, AY, math.radians(40)), closed=True),
        fill=ACCENT_6,
        stroke=ACCENT,
        stroke_width=3,
        stroke_linejoin="round",
    )

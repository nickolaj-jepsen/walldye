"""Flat walls after Luis Barragán stand at the edge of a still pool, mirrored below in horizontal ripple strips that widen and waver towards the viewer."""

import math

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    ACCENT_HI,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    P,
    by_regime,
    design,
    mix,
)

REACH = 480  # the long wall and the pool start this far left of the tall wall
DEPTH = 260  # pool depth on screen; under the long wall's 280, so every reflection runs off
SLOPE = 0.55  # sun from upper left: shadow edges run down-right at dx/dy
CALM = 0.6  # the long wall's reflection ripples less, so the accent walls' stay the lively surface
# Shadows step towards the foreground on light themes, where the dark ramp steps turn pale.
FOOT = by_regime(ACCENT_1, ACCENT_HI)  # the tall wall's foot shadow
CAST = by_regime(BG_ALT, UI_ALT)  # the side wall's shadow on the long wall
# Reflection fills, one bucket per mirrored shape, back to front: long wall, side wall, tall wall,
# CAST, FOOT, the doorway.
WATER = (
    BG_ALT,
    ACCENT_6,
    ACCENT_5,
    by_regime(mix(BG_DEEP, BG_ALT, 0.45), mix(BG_ALT, UI, 0.45)),
    by_regime(ACCENT_6, ACCENT_4),
    BG_DEEP,
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # x: the tall wall's left edge; wl: the waterline every wall stands on
    x = s.pick(landscape=(1180 / 1920, 0), portrait=(0.39, 0), snap=1).x
    wl = s.h - DEPTH
    pool = x - REACH  # rim under the long wall's left end; off-frame on portrait screens
    long_top, side_top, tall_top = wl - 280, wl - 420, wl - 650
    foot_top = wl - 220  # the tall wall's foot shadow
    door = (x - 300, x - 190, wl - 180)

    # drawn back to front; the long wall runs off-frame
    for left, right, top, face in (
        (pool, s.w + 60, long_top, UI),
        (x + 240, x + 400, side_top, ACCENT_3),
        (x, x + 240, tall_top, ACCENT),
    ):
        s.fill(P().rect(left, top, right - left, wl - top), face)
    for foot, top, face in ((x, foot_top, FOOT), (x + 400, long_top, CAST)):
        s.fill(
            P().poly([(foot, top), (foot + SLOPE * (wl - top), wl), (foot, wl)], closed=True), face
        )
    s.fill(P().rect(door[0], door[2], door[1] - door[0], wl - door[2]), BG)
    s.fill(P().rect(pool, wl, s.w - pool, s.h - wl), BG_DEEP)

    # (left, right at the waterline, lean, depth, lively) in WATER order: each mirrored shape
    # narrows by `lean` per unit of depth and ends `depth` below the waterline
    images = (
        (pool, s.w + 60, 0, wl - long_top, False),
        (x + 240, x + 400, 0, wl - side_top, True),
        (x, x + 240, 0, wl - tall_top, True),
        (x + 400, x + 400 + SLOPE * (wl - long_top), SLOPE, wl - long_top, False),
        (x, x + SLOPE * (wl - foot_top), SLOPE, wl - foot_top, True),
        (door[0], door[1], 0, wl - door[2], False),
    )
    rng = s.np_rng(11)
    with s.buckets(WATER, "fill") as water:
        y, row = wl, 0
        while y < s.h:
            d = y - wl
            step = 4 + d / 60  # ripple bands widen towards the viewer
            # still at the waterline, rippling more with distance
            dx = (0.3 + d / 70) * (1.6 * math.sin(d * 0.19) + rng.normal(0, 0.6))
            for i, (left, right, lean, depth, lively) in enumerate(images):
                if d >= depth:
                    continue
                shift = dx if lively else dx * CALM
                # an edge standing on the pool rim is pushed past it, so the rim, not the jitter,
                # sets it
                a = max(pool, (left - 60 if left <= pool else left) + shift)
                b = min(s.w, right - lean * d + shift)
                if b > a:
                    # calm layers keep every other gap closed, halving the stripe count
                    water[i].rect(a, y, b - a, step * (0.82 if lively or row % 2 else 1))
            y, row = y + step, row + 1
    s.stroke(P().M(pool, wl).H(s.w), UI_ALT, 2)

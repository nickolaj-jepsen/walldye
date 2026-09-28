"""A keyboard corner seen from above: keycaps as four stacked rounded rectangles, the Escape key picked out and the rest fading with distance from it."""

import math

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_HI,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    Colour,
    P,
    Vec,
    design,
    mix,
)
from walldye.geom import Affine

U = 150  # one key unit
ANGLE = 11  # board tilt, clockwise
# Tenkeyless ANSI: (row y, key widths), both in units; negative widths are gaps.
ROWS = (
    (0.0, (1, -1, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.25, 1, 1, 1)),
    (1.5, (1,) * 13 + (2, -0.25, 1, 1, 1)),
    (2.5, (1.5,) + (1,) * 12 + (1.5, -0.25, 1, 1, 1)),
    (3.5, (1.75,) + (1,) * 11 + (2.25,)),
    (4.5, (2.25,) + (1,) * 10 + (2.75, -1.25, 1)),
    (5.5, (1.25,) * 3 + (6.25,) + (1.25,) * 4 + (-0.25, 1, 1, 1)),
)
BOARD = (18.25, 6.5)  # key area in units
# Keycap layers in a 110-wide drawing of one unit cell: (left, top, width cut, height cut, radius).
# The top face sits back from the cell centre so its front wall shows, and the dish is shadowed
# at its back wall.
LAYERS = (
    (5, 5, 10, 10, 12),  # skirt
    (17, 11, 34, 34, 10),  # top face
    (24, 17, 48, 48, 9),  # dish
    (25, 21, 50, 53, 8),  # dish floor
)


def shading(skirt: Colour, top: Colour, lift: Colour) -> tuple[Colour, ...]:
    """One plastic's paints for LAYERS, bottom to top."""
    return (skirt, top, mix(top, skirt, 0.4), mix(top, lift, 0.15))


# The accent Escape key, then three UI sets that sink towards the board with distance from it.
PAINTS = (
    *shading(mix(ACCENT_2, ACCENT_3, 0.45), ACCENT, mix(ACCENT, ACCENT_HI, 0.4)),
    *shading(BG_ALT, UI, UI_ALT),
    *shading(mix(BG_ALT, BG_DEEP, 0.15), mix(UI, BG_ALT, 0.25), UI_ALT),
    *shading(mix(BG_ALT, BG_DEEP, 0.3), mix(UI, BG_ALT, 0.5), UI_ALT),
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # The board runs off the right and bottom edges; wide screens keep the 16:9 crop on the
    # right and leave the extra width empty, and portrait screens show more rows.
    esc = Vec(max(420, s.w - 1500), s.h - (420 if s.landscape else 720))
    frame = Affine.frame(esc, deg=ANGLE)
    k = U / 110
    with s.group(transform=frame):
        s.path(
            P().rrect(-U / 2 - 40, -U / 2 - 40, BOARD[0] * U + 80, BOARD[1] * U + 80, 30),
            fill=BG_DEEP,
            stroke=UI,
            stroke_width=2,
        )
        with s.buckets(PAINTS, "fill") as caps:
            for y, widths in ROWS:
                x = 0.0
                for w in widths:
                    if w > 0 and s.inset(-(w / 2 + 1) * U).contains(
                        frame(((x + w / 2 - 0.5) * U, y * U))
                    ):
                        dist = math.hypot(x + w / 2 - 0.5, y)
                        tone = 0 if x == y == 0 else 1 + (dist > 3) + (dist > 6)
                        px, py = (x - 0.5) * U, (y - 0.5) * U
                        for i, (left, top, dw, dh, r) in enumerate(LAYERS):
                            caps[4 * tone + i].rrect(
                                px + left * k, py + top * k, w * U - dw * k, U - dh * k, r * k
                            )
                    x += abs(w)

"""A drag strip's starting tree at a handicap start, as LED clusters on one pixel grid."""

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_4,
    ACCENT_6,
    BG_ALT,
    UI,
    Canvas,
    design,
)
from walldye.pixel import Pixels, glyphs

type Mask = NDArray[np.bool_]

CELL = 3
R, RS = 17, 8  # lamp radius in cells: countdown, go and foul lamps; staging bulbs
LED, DX, DY = 2, 4, 3  # an LED is LED x LED cells, DX apart along a row and rows DY apart
SPINE = 44  # the width in cells of the column the lane lamps hang either side of
REACH = SPINE // 2  # lamp centres sit on the column's edges
STEP = 40  # between lamp centres down a lane
W = 2 * (REACH + R + 4)
BAR, PAD = 9, 2  # the height of a label's band; the clearance round each staging bulb
POLE = 6

NONE, PLATE, EDGE, DARK, HALO, LENS, LIT, WAIT = range(8)
PALETTE = (None, BG_ALT, UI, UI, ACCENT_6, ACCENT_3, ACCENT, ACCENT_4)


def disc(ys: NDArray[np.float64], xs: NDArray[np.float64], cx: int, cy: int, r: float) -> Mask:
    """Cells whose centres lie within r of the grid vertex (cx, cy)."""
    return np.hypot(xs + 0.5 - cx, ys + 0.5 - cy) < r


def leds(cx: int, cy: int, r: float) -> list[tuple[int, int]]:
    """Top-left cells of a lamp's LEDs, hex-packed about the grid vertex (cx, cy): rows DY
    apart, LEDs DX apart, every other row shifted by half, kept within radius r. A row that
    would hold a single LED is left out, since a lone pip reads as a stray mark."""
    out: list[tuple[int, int]] = []
    n = int(r // DY)
    for j in range(-n, n + 1):
        shift = DX // 2 * (j % 2)
        offs = [i * DX + shift for i in range(-int(r // DX) - 1, int(r // DX) + 1)]
        row = [
            (cx + x - LED // 2, cy + j * DY - LED // 2)
            for x in offs
            if x * x + (j * DY) ** 2 <= r * r
        ]
        if len(row) > 1:
            out += row
    return out


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the staging head, row by row: a label, the pre-stage bulbs, a rule, then a label and the
    # stage bulbs; a bulb spans rows cy - RS to cy + RS - 1
    cy1 = 1 + BAR + 1 + PAD + RS
    bars = (1, cy1 + RS + PAD + 1)
    cy2 = bars[1] + BAR + 1 + PAD + RS
    head_h = cy2 + RS + PAD + 1
    y0 = head_h + R + 6
    foot = y0 + 4 * STEP + R + 7
    top = s.pick(landscape=(0.66, 0.11), portrait=(0.66, 0.36), snap=CELL)
    ox, oy = int(top.x) - W // 2 * CELL, int(top.y)
    cols, rows = W, (s.h - oy) // CELL + 1
    px = Pixels(cols, rows, PALETTE)
    ys, xs = np.mgrid[0:rows, 0:cols].astype(np.float64)
    g = px.grid

    mid = W // 2
    lanes = (mid - REACH, mid + REACH)
    sp0, sp1 = mid - SPINE // 2, mid + SPINE // 2

    def box(x0: int, y0: int, x1: int, y1: int) -> None:
        """A plate with an outline, open at the bottom when it runs off the grid."""
        g[y0:y1, x0:x1] = PLATE
        g[y0, x0:x1] = EDGE
        if y1 <= rows:
            g[y1 - 1, x0:x1] = EDGE
        g[y0:y1, [x0, x1 - 1]] = EDGE

    # housing: the staging head, the column below it and the pole running off the bottom edge
    box(sp0, head_h - 1, sp1, foot)
    box(mid - POLE // 2, foot - 1, mid + POLE // 2, rows + 1)
    box(0, 0, W, head_h)
    g[bars[1] - 1, 1:-1] = EDGE

    def lamp(cx: int, cy: int, r: int, led: int) -> None:
        body = disc(ys, xs, cx, cy, r)
        if led == LIT:
            g[disc(ys, xs, cx, cy, r + 2) & ~body] = HALO
            g[body] = LENS
        else:
            g[body] = NONE
            # a 2-cell rim on the big lamps and 1 on the staging bulbs
            g[body & ~disc(ys, xs, cx, cy, r - r // 8)] = EDGE
        for x, y in leds(cx, cy, r - 4):
            g[y : y + LED, x : x + LED] = led

    # A handicap start: the left car got its countdown first and has left the staging beams, so
    # its staging bulbs are out and only its go lamp shows; the right car still sits staged.
    for lx in lanes:
        for cy in (cy1, cy2):
            for dx in (-RS - 1, RS + 1):
                lamp(lx + dx, cy, RS, WAIT if lx == lanes[1] else DARK)
        for k in range(5):
            lamp(lx, y0 + k * STEP, R, LIT if lx == lanes[0] and k == 3 else DARK)

    px.draw(s, CELL, (ox, oy))
    # labels in cell-sized font pixels, on the same grid as the lamps; a 5x8 capital fills
    # font rows 1 to 6, so each sits 2 rows under the rule above it
    for text, y in zip(("PRE-STAGE", "STAGE"), bars, strict=True):
        n = len(text) * 6 - 1
        glyphs(
            s,
            text,
            UI,
            at=(ox + (mid - n // 2) * CELL, oy + (y + 1) * CELL),
            font="5x8",
            px=CELL,
            gap=1,
        )
